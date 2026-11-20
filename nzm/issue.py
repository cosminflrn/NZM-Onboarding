"""Parse a GitHub issue-form body (env ISSUE_BODY) into GITHUB_OUTPUT values."""
import os
import re

FIELDS = {"link site": "url", "nume brand": "name", "cod discount": "discount", "email expeditor": "sender_email"}


def parse(body):
    out = {v: "" for v in FIELDS.values()}
    for block in re.split(r"^###\s+", body or "", flags=re.M)[1:]:
        label, _, value = block.partition("\n")
        value = value.strip()
        if value in ("_No response_", "None"):
            value = ""
        for key, name in FIELDS.items():
            if label.strip().lower().startswith(key):
                out[name] = value.splitlines()[0].strip() if value else ""
    return out


if __name__ == "__main__":
    vals = parse(os.environ.get("ISSUE_BODY", ""))
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
        for k, v in vals.items():
            v = re.sub(r"[\r\n]", " ", v)
            f.write(f"{k}={v}\n")
    print(vals)
