import json
import os
import re

log_file = r'C:\Users\talha\.gemini\antigravity\brain\53f78928-3729-4a5d-897b-e49e8cfe8ac2\.system_generated\logs\overview.txt'

for line in open(log_file, encoding='utf-8'):
    try:
        data = json.loads(line)
        
        # Check tool responses for view_file
        if data.get("type") == "TOOL_RESPONSE":
            for call in data.get("tool_calls", []):
                if call.get("name") == "view_file":
                    output = call.get("response", {}).get("output", "")
                    if "Showing lines" in output:
                        # Extract file path
                        match = re.search(r"File Path: `file:///(.*?)`", output)
                        if match:
                            path = match.group(1).replace("%C3%BC", "ü").replace("/", "\\")
                            if "scrapers" in path:
                                print(f"Found view_file content for: {path}")
                                # extract the code (remove line numbers)
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
                                        # format is "1: code..."
                                        m = re.match(r"^\d+: (.*)", out_line)
                                        if m:
                                            code_lines.append(m.group(1))
                                        elif out_line == "":
                                            pass
                                        else:
                                            code_lines.append(out_line)
                                
                                # Replace networkidle with domcontentloaded
                                content = "\n".join(code_lines).replace('networkidle', 'domcontentloaded')
                                
                                # write file
                                with open(path, "w", encoding="utf-8") as f:
                                    f.write(content)
                                print(f"Restored {path} from view_file")

        # Check tool calls for write_to_file
        if data.get("type") == "PLANNER_RESPONSE":
            for call in data.get("tool_calls", []):
                if call.get("name") == "write_to_file":
                    args = call.get("args", {})
                    path = args.get("TargetFile", "")
                    content = args.get("CodeContent", "")
                    if "scrapers" in path and content:
                        print(f"Found write_to_file content for: {path}")
                        content = content.replace('networkidle', 'domcontentloaded')
                        with open(path, "w", encoding="utf-8") as f:
                            f.write(content)
                        print(f"Restored {path} from write_to_file")
    except Exception as e:
        pass

print("Done restoring files.")
