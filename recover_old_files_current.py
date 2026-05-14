import json
import os
import re

log_file = r'C:\Users\talha\.gemini\antigravity\brain\53f78928-3729-4a5d-897b-e49e8cfe8ac2\.system_generated\logs\overview.txt'

found_count = 0
for line in open(log_file, encoding='utf-8'):
    if "keskin.py" not in line and "koc.py" not in line and "base.py" not in line and "mollaoglu.py" not in line:
        continue
        
    try:
        data = json.loads(line)
        output = data.get("content", "")
        if not output:
            output = data.get("response", {}).get("output", "")
            
        if not output and "tool_calls" in data:
            for call in data["tool_calls"]:
                out = call.get("response", {}).get("output", "")
                if out:
                    output += out + "\n"
                    
        if "Showing lines" in output:
            match = re.search(r"File Path: `file:///(.*?)`", output)
            if match:
                path = match.group(1).replace("%C3%BC", "ü").replace("/", "\\")
                if "scrapers" in path and ("keskin" in path or "koc" in path or "base" in path or "mollaoglu" in path or "netlastik" in path or "tiryakiler" in path or "otosemih" in path):
                    print(f"Found view_file content for: {path}")
                    code_lines = []
                    in_code = False
                    for out_line in output.split('\n'):
                        if out_line.startswith("The following code has been modified"):
                            in_code = True
                            continue
                        if out_line.startswith("The above content shows"):
                            in_code = False
                            continue
                        if in_code:
                            m = re.match(r"^\d+: (.*)", out_line)
                            if m:
                                code_lines.append(m.group(1))
                            elif out_line == "":
                                pass
                            else:
                                code_lines.append(out_line)
                    
                    content = "\n".join(code_lines).replace('networkidle', 'domcontentloaded')
                    if len(content) > 100:
                        with open(path, "w", encoding="utf-8") as f:
                            f.write(content)
                        print(f"Restored {path} from view_file")
                        found_count += 1

        # Also check write_to_file calls!
        if "tool_calls" in data:
            for call in data["tool_calls"]:
                if call.get("name") == "write_to_file":
                    args = call.get("args", {})
                    if "TargetFile" in args and "CodeContent" in args:
                        path = args["TargetFile"]
                        content = args["CodeContent"]
                        if "scrapers" in path and ("keskin" in path or "koc" in path or "base" in path or "mollaoglu" in path or "netlastik" in path or "tiryakiler" in path or "otosemih" in path):
                            print(f"Found write_to_file content for: {path}")
                            content = content.replace('networkidle', 'domcontentloaded')
                            if len(content) > 100:
                                with open(path.replace('\"', ''), "w", encoding="utf-8") as f:
                                    f.write(content)
                                print(f"Restored {path} from write_to_file")
                                found_count += 1
    except Exception as e:
        pass

print(f"Done restoring {found_count} files.")
