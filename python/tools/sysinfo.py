"""Read-only hardware/OS report for this Windows PC (2026-11-22). Changes nothing.
Run through the watcher job 'sysinfo'; output in remote/logs/ and results/sysinfo.txt."""
import subprocess, json, pathlib

Q = {
    'Computer': "Get-CimInstance Win32_ComputerSystem | Select Manufacturer,Model,TotalPhysicalMemory,NumberOfProcessors",
    'OS': "Get-CimInstance Win32_OperatingSystem | Select Caption,Version,BuildNumber,OSArchitecture,LastBootUpTime",
    'CPU': "Get-CimInstance Win32_Processor | Select Name,NumberOfCores,NumberOfLogicalProcessors,MaxClockSpeed,L2CacheSize,L3CacheSize",
    'Motherboard': "Get-CimInstance Win32_BaseBoard | Select Manufacturer,Product,Version",
    'BIOS': "Get-CimInstance Win32_BIOS | Select Manufacturer,SMBIOSBIOSVersion,ReleaseDate",
    'RAM sticks': "Get-CimInstance Win32_PhysicalMemory | Select BankLabel,DeviceLocator,Manufacturer,PartNumber,Capacity,Speed,ConfiguredClockSpeed",
    'GPU': "Get-CimInstance Win32_VideoController | Select Name,DriverVersion,CurrentHorizontalResolution,CurrentVerticalResolution,CurrentRefreshRate",
    'Physical disks': "Get-PhysicalDisk | Select FriendlyName,MediaType,BusType,Size,HealthStatus",
    'Volumes': "Get-Volume | Where DriveLetter | Select DriveLetter,FileSystemLabel,FileSystem,Size,SizeRemaining,HealthStatus | Sort DriveLetter",
    'Network adapters': "Get-NetAdapter | Where Status -eq Up | Select Name,InterfaceDescription,LinkSpeed",
}
out = []
for k, cmd in Q.items():
    r = subprocess.run(['powershell', '-NoProfile', '-Command', cmd + ' | ConvertTo-Json -Depth 3'],
                       capture_output=True, text=True, timeout=60)
    out.append(f'== {k}\n' + (r.stdout.strip() or r.stderr.strip()))
try:
    r = subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total,driver_version,pcie.link.gen.max,pcie.link.width.max,power.limit,clocks.max.sm,clocks.max.mem',
                        '--format=csv'], capture_output=True, text=True, timeout=30)
    out.append('== nvidia-smi\n' + r.stdout.strip())
except Exception as e:
    out.append(f'== nvidia-smi\n{e}')
txt = '\n'.join(out); print(txt)
pathlib.Path('results').mkdir(exist_ok=True)
pathlib.Path('results/sysinfo.txt').write_text(txt + '\n', encoding='utf-8')
print('SYSINFO_DONE')
