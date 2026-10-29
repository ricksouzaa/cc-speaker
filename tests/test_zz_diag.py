import os, shutil, subprocess, sys, tempfile, unittest

class Diag(unittest.TestCase):
    def test_diag(self):
        d = tempfile.mkdtemp()
        code = ('import os,subprocess;'
                'print(subprocess.run(["ps","-o","pid=,ppid=,comm=,command=","-p",str(os.getpid())],'
                'capture_output=True,text=True).stdout.strip(), "| exe=", __import__("sys").executable)')
        cands = {}
        a = os.path.join(d, 'claude'); os.symlink(sys.executable, a); cands['symlink-exe'] = a
        real = os.path.realpath(sys.executable)
        b = os.path.join(d, 'claude2'); os.symlink(real, b); cands['symlink-real'] = b
        c = os.path.join(d, 'c3', 'claude'); os.makedirs(os.path.dirname(c)); shutil.copy2(sys.executable, c); cands['copy-exe'] = c
        e = os.path.join(d, 'c4', 'claude'); os.makedirs(os.path.dirname(e)); shutil.copy2('/bin/sleep', e); cands['copy-sleep'] = e
        f = os.path.join(d, 'c5', 'claude'); os.makedirs(os.path.dirname(f)); shutil.copy2('/bin/sh', f); cands['copy-sh'] = f
        print('\nDIAG platform', sys.platform, 'executable', sys.executable, 'real', real)
        for k, p in cands.items():
            if k == 'copy-sleep':
                r = subprocess.Popen([p, '5']); 
                import time; time.sleep(0.5)
                o = subprocess.run(['ps', '-o', 'pid=,ppid=,comm=,command=', '-p', str(r.pid)], capture_output=True, text=True)
                r.kill(); r.wait()
                print('DIAG', k, o.returncode, o.stdout.strip(), o.stderr.strip())
            elif k == 'copy-sh':
                o = subprocess.run([p, '-c', 'ps -o pid=,ppid=,comm=,command= -p $$'], capture_output=True, text=True)
                print('DIAG', k, o.returncode, o.stdout.strip(), o.stderr.strip())
            else:
                try:
                    o = subprocess.run([p, '-I', '-c', code], capture_output=True, text=True, timeout=20)
                    print('DIAG', k, o.returncode, o.stdout.strip(), o.stderr.strip()[:300])
                except Exception as x:
                    print('DIAG', k, 'EXC', x)
        shutil.rmtree(d)
