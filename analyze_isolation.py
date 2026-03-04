import os, glob

fails = []
passes = []

base = "per_proportion_reports/2026-02-25_002652/deltablue"
for p in glob.glob(f"{base}/*/*/run_stdout.txt"):
    with open(p) as f:
        content = f.read()
    source = p.replace("run_stdout.txt", "source.py")
    if not os.path.exists(source): continue
    with open(source) as f: lines = f.readlines()
        
    detyped = set()
    for i, line in enumerate(lines):
        if "types_removed" in line:
            j = i + 1
            while j < len(lines) and lines[j].strip().startswith("@"): j += 1
            if j < len(lines):
                func_def = lines[j].strip()
                if func_def.startswith("def "):
                    detyped.add(func_def.split("def ")[1].split("(")[0])
                elif func_def.startswith("class "):
                    detyped.add(func_def.split("class ")[1].split("(")[0].split(":")[0])
                    
    if "Chain test failed" in content:
        fails.append(detyped)

unexplained = [f for f in fails if "add_constraints_consuming_to" not in f and "make_plan" not in f]
print(f"Unexplained fails: {len(unexplained)} out of {len(fails)}")

