import json
import os
if os.path.exists("tmp_data.json"):
    os.remove("tmp_data.json")

with open("tmp_data.json", "w") as json_file:
    json.dump(tmp_data, json_file)