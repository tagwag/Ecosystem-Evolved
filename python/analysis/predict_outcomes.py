"""Can the outcome of an evolution run be predicted from its early generations? (analysis of saved results only)
Data: per-generation training curves of every run with a saved history (connectome Steps 19-22, toy-brain 900 / 3200).
Target: a run's FINAL level = mean of its last 20 generations (first 300 generations only, so runs are comparable).
Predictors, all using only generations < k:
  persistence   "it stays where it is": mean of generations k-10..k
  family gain   persistence + the average further gain of OTHER experiment families from k to the end
  ridge         linear model on [level now, slope so far, starting level, best so far, noise], trained on other families
  curve fit     saturating curve y = a - b*exp(-g/tau) fitted to the run's own first k generations, read off at the end
Honest test: leave one experiment FAMILY out (train on the rest), so the model never sees the experiment it predicts.
Skill score R2 is computed WITHIN each arm (how well it ranks / places seeds of the same arm) and ACROSS arms."""
import json, numpy as np
from scipy.optimize import curve_fit
from scipy import stats
U=''   # run from the python/ folder:  python analysis/predict_outcomes.py   (needs results/_histories_all.json, see analysis/README.md)
H=json.load(open(U+'results/_histories_all.json'))
runs=[]   # (family, arm, seed, curve)
for arm,seeds in H.items():
    fam=arm.split('/')[0]
    for s,r in seeds.items(): runs.append((fam,arm,s,np.array(r['fitness'],float)))
for tag,fn in (('toy900','toybrain/results_gpu_900g_30s_fair.json'),('toy3200ref','toybrain/results_gpu_3200g_30s_fair.json')):
    d=json.load(open(U+fn))
    for c in d:
        if c=='random_walk': continue
        for i,cv in enumerate(d[c]['curves']): runs.append(('toy',f'{tag}/{c}',str(i),np.array(cv,float)))
T=190                      # common horizon: every run has at least 190 generations
runs=[r for r in runs if len(r[3])>=T]
fams=sorted({r[0] for r in runs}); print('families',{f:sum(r[0]==f for r in runs) for f in fams},'runs',len(runs),'horizon',T)
Y=np.array([r[3][T-20:T].mean() for r in runs]); fam=np.array([r[0] for r in runs]); arm=np.array([r[1] for r in runs])
# scale per family (connectome fitness ~2-3, toy food ~30-110): work in units of the family's final spread around 0-1
def feats(c,k):
    x=c[:k]; g=np.arange(k)
    return [x[-10:].mean(), np.polyfit(g[-max(10,k//2):],x[-max(10,k//2):],1)[0]*100, x[:5].mean(), x.max(), x[-10:].std()]
def sat(g,a,b,tau): return a-b*np.exp(-g/tau)
def curvefit(c,k):
    g=np.arange(k)
    try:
        p,_=curve_fit(sat,g,c[:k],p0=[c[k-10:k].mean()*1.05,max(c[k-10:k].mean()-c[:3].mean(),1e-3),max(k/3,5)],maxfev=4000,bounds=([0,0,2],[c.max()*3+1,c.max()*3+1,5000]))
        return float(np.mean(sat(np.arange(T-20,T),*p)))
    except Exception: return float(c[k-10:k].mean())
def r2(y,p): 
    ss=((y-y.mean())**2).sum(); return float(1-((y-p)**2).sum()/ss) if ss>0 else float('nan')
res={}
for k in (10,20,50,100):
    X=np.array([feats(r[3],k) for r in runs]); pers=X[:,0]; P={m:np.zeros(len(runs)) for m in ('persistence','family gain','ridge','curve fit')}
    P['persistence']=pers.copy(); P['curve fit']=np.array([curvefit(r[3],k) for r in runs])
    for f in fams:
        te=fam==f; tr=~te
        # relative units so families with different scales can teach each other: divide by level now
        gain=np.mean((Y[tr]-pers[tr])/np.maximum(pers[tr],1e-6)); P['family gain'][te]=pers[te]*(1+gain)
        A=np.c_[np.ones(tr.sum()), X[tr,1]/np.maximum(pers[tr],1e-6), X[tr,2]/np.maximum(pers[tr],1e-6), X[tr,3]/np.maximum(pers[tr],1e-6), X[tr,4]/np.maximum(pers[tr],1e-6)]
        yy=Y[tr]/np.maximum(pers[tr],1e-6); lam=1.0
        w=np.linalg.solve(A.T@A+lam*np.eye(A.shape[1]),A.T@yy)
        B=np.c_[np.ones(te.sum()), X[te,1]/np.maximum(pers[te],1e-6), X[te,2]/np.maximum(pers[te],1e-6), X[te,3]/np.maximum(pers[te],1e-6), X[te,4]/np.maximum(pers[te],1e-6)]
        P['ridge'][te]=(B@w)*pers[te]
    out={}
    for m,p in P.items():
        # relative error (% of the true final level), R2 within arm (pooled, after removing each arm's mean), rank agreement within arm
        rel=np.abs(p-Y)/np.abs(Y); 
        yc=np.concatenate([Y[arm==a]-Y[arm==a].mean() for a in np.unique(arm)]); pc=np.concatenate([p[arm==a]-p[arm==a].mean() for a in np.unique(arm)])
        am_y=np.array([Y[arm==a].mean() for a in np.unique(arm)]); am_p=np.array([p[arm==a].mean() for a in np.unique(arm)]); af=np.array([a.split('/')[0] for a in np.unique(arm)])
        rho=np.mean([stats.spearmanr(Y[arm==a],p[arm==a]).statistic for a in np.unique(arm)])
        # arm-level: within each family, does the predicted arm ranking match the final arm ranking?
        armrho=[stats.spearmanr(am_y[af==f],am_p[af==f]).statistic for f in np.unique(af) if (af==f).sum()>=3]
        out[m]=dict(median_err_pct=float(np.median(rel)*100), p90_err_pct=float(np.percentile(rel,90)*100), r2_within_arm=r2(yc,pc), seed_rank_rho=float(rho), arm_rank_rho=float(np.mean(armrho)))
    res[k]=out
    print(f'\n== using the first {k} generations to predict generation {T}')
    for m,o in out.items(): print(f"  {m:12s} median error {o['median_err_pct']:5.1f} %   90th pct {o['p90_err_pct']:5.1f} %   R2 within arm {o['r2_within_arm']:+.2f}   seed rank rho {o['seed_rank_rho']:+.2f}   arm rank rho {o['arm_rank_rho']:+.2f}")
# how much of the final spread between seeds of one arm is luck that early generations cannot see? repeatability
print('\nper family, seed-rank agreement (persistence) at k=20 / 100:')
for f in fams:
    for k in (20,100):
        v=[stats.spearmanr(Y[arm==a],[r[3][k-10:k].mean() for r in runs if r[1]==a]).statistic for a in np.unique(arm[fam==f])]
        print(f'  {f} k={k}: {np.mean(v):+.2f}', end='')
    print()
# noise floor: generation-to-generation wobble of a finished run vs spread between seeds
wob=np.array([r[3][T-20:T].std() for r in runs])/Y; spread=np.array([Y[arm==a].std()/Y[arm==a].mean() for a in np.unique(arm)])
print('within-run wobble at the end (CV) median %.1f %%; between-seed spread within an arm (CV) median %.1f %%'%(np.median(wob)*100,np.median(spread)*100))
json.dump(res,open('results/predict_outcomes.json','w'))
