import os, glob

fails = []
passes = []

base = "per_proportion_reports/2026-02-25_002652/deltablue"
for p in glob.glob(f"{base}/*/*/run_stdout.txt"):
    with open(p) as f:
        content = f.read()
    
    source = p.replace("run_stdout.txt", "source.py")
    if not os.path.exists(source):
        continue
    with open(source) as f:
        lines = f.readlines()
        
    detyped_funcs = set()
    for i, line in enumerate(lines):
        if "types_removed" in line:
            func_def_line = lines[i+1].strip()
            if func_def_line.startswith("def "):
                func_name = func_def_line.split("def ")[1].split("(")[0]
                detyped_funcs.add(func_name)
            elif func_def_line.startswith("@"):
                # sometimes there are decorators
                j = i + 1
                while lines[j].strip().startswith("@"):
                    j += 1
                func_def_line = lines[j].strip()
                if func_def_line.startswith("def "):
                    func_name = func_def_line.split("def ")[1].split("(")[0]
                    detyped_funcs.add(func_name)
                
    if "Chain test failed" in content:
        fails.append(detyped_funcs)
    else:
        passes.append(detyped_funcs)

counts = {}
for funcs in fails:
    for f in funcs:
        counts.setdefault(f, {'fail': 0, 'pass': 0})
        counts[f]['fail'] += 1
for funcs in passes:
    for f in funcs:
        counts.setdefault(f, {'fail': 0, 'pass': 0})
        counts[f]['pass'] += 1

print(f"Total fails: {len(fails)}")
print(f"Total passes: {len(passes)}")
print("--- Fails vs Passes when detyped ---")
for f, c in sorted(counts.items(), key=lambda x: x[1]['fail']/(x[1]['fail']+x[1]['pass']), reverse=True):
    if c['fail'] > 0:
        ratio = c['fail'] / (c['fail'] + c['pass']) * 100
        print(f"{f}: fail={c['fail']} pass={c['pass']} ({ratio:.1f}% fail rate when detyped)")
