#!/usr/bin/env python3
import json
from typing import Any


def accounts():
    ret = []
    with open("accounts.json", "r") as f:
        st = f.read()
    l: list[dict[str, Any]] = json.loads(st)
    for acct in l:
        a = acct["addresses"]["entities"]
        if a:
            ret.append(acct)

    with open("accounts_without_inventory.csv", "w") as f:
        f.write("name,id\r\n")
        for a in ret:
            f.write(f'{a["name"]},{a["id"]}\r\n')

    ret = []
    with open("inventory.json", "r") as f:
        st = f.read()
    l: list[dict[str, Any]] = json.loads(st)

    with open("inventory_without_accounts.csv", "w") as f:
        f.write("id,mac address,info\r\n")
        for a in l:
            t = {"id": a["id"]}
            m = a["inventory_model_field_data"]["entities"]
            if m[0]["inventory_model_field"]["name"].lower() == "mac":
                t["mac"] = m[0]["value"]
                t["info"] = m[1]["value"]
            else:
                t["mac"] = m[1]["value"]
                t["info"] = m[0]["value"]
            f.write(f'{t["id"]},{t["mac"]},{t["info"]}\r\n')

    return ret
