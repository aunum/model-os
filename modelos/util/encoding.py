from typing import List, Dict


def list_to_str(lis: List[str]) -> str:
    return ",".join(lis)


def str_to_list(s: str) -> List[str]:
    lis = s.split(",")
    if len(lis) == 1 and lis[0] == "":
        return []
    return lis


def dict_to_str(d: Dict[str, str]) -> str:
    ret_lis = []
    for k, v in d.items():
        ret_lis.append(f"{k}:{v}")

    return " | ".join(ret_lis)


def str_to_dict(s: str) -> Dict[str, str]:
    kvs = s.split(" | ")

    ret: Dict[str, str] = {}
    for kv in kvs:
        kv_parts = kv.split(":")
        if len(kv_parts) != 2:
            continue
        ret[kv_parts[0]] = kv_parts[1]
    return ret
