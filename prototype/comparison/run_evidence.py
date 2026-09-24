"""Local real-window evidence. Requires Godot, never calls a paid service."""
import argparse, json, subprocess, time, platform, statistics
from pathlib import Path
HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent / 'godot'
ROUTES = ('baseline', '3d', '2d', 'pixel')
p = argparse.ArgumentParser()
p.add_argument('--godot', default='/Applications/Godot.app/Contents/MacOS/Godot')
p.add_argument('--performance', action='store_true')
a = p.parse_args()
out = HERE / 'evidence'; out.mkdir(exist_ok=True)
logs = HERE / 'logs'; logs.mkdir(exist_ok=True)
def command(route, size, phase):
    return [a.godot, '--path', str(PROJECT), 'res://comparison/main.tscn', '--', f'--route={route}', f'--size={size}', f'--phase={phase}', f'--out={out}']
if not a.performance:
    records=[]
    for route in ROUTES:
        for size in ('1280x720','800x600','360x320'):
            for phase in ('day','evening'):
                proof = phase == 'day'
                name=f'{route}-{size}-{phase}'
                start=time.monotonic()
                result=subprocess.run(command(route,size,phase)+['--proof' if proof else '--capture','--quit'],capture_output=True,text=True,timeout=35)
                log=result.stdout+result.stderr
                # Paths in engine capture output are local diagnostics; make shared logs relative.
                log=log.replace(str(HERE.parent.parent),'<repo>')
                (logs/f'{name}.log').write_text(log)
                ok=result.returncode==0 and 'SCRIPT ERROR' not in log and 'ERROR:' not in log and (not proof or 'COMPARISON_PROOF_PASS' in log)
                records.append({'run':name,'ok':ok,'wall_seconds':round(time.monotonic()-start,3)})
                print(name,ok,flush=True)
                if not ok: raise SystemExit(log)
    (out/'matrix.json').write_text(json.dumps(records,indent=2))
else:
    report={'platform':platform.system(),'release':platform.release(),'machine':platform.machine(),'fps_cap':30,'size':[360,320],'phase':'day','warmup_seconds':30,'sample_seconds':60,'cpu_unit':'ps %CPU; 100% = one core; OS estimate, not instantaneous total system CPU','routes':{}}
    for route in ROUTES:
        with (logs/f'{route}-perf.log').open('w') as log:
            proc=subprocess.Popen(command(route,'360x320','day')+['--telemetry'],stdout=log,stderr=subprocess.STDOUT)
            try:
                time.sleep(30)
                samples=[]
                for i in range(60):
                    if proc.poll() is not None: raise RuntimeError('renderer exited')
                    raw=subprocess.check_output(['ps','-p',str(proc.pid),'-o','%cpu=,rss='],text=True).split()
                    samples.append({'second':i,'cpu_percent':float(raw[0]),'rss_kib':int(raw[1])})
                    time.sleep(1)
                cpu=[s['cpu_percent'] for s in samples];rss=[s['rss_kib']/1024 for s in samples]
                report['routes'][route]={'samples':samples,'cpu_median':statistics.median(cpu),'cpu_peak':max(cpu),'rss_mib_median':statistics.median(rss),'rss_mib_peak':max(rss)}
                report['routes'][route]['engine_frames']=json.loads((out/f'{route}-idle-frames.json').read_text())
                (out/'performance.json').write_text(json.dumps(report,indent=2))
                print(route,report['routes'][route]['cpu_median'],flush=True)
            finally:
                proc.terminate()
                try: proc.wait(10)
                except subprocess.TimeoutExpired: proc.kill(); proc.wait()
