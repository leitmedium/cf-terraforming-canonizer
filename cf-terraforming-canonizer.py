#!/usr/bin/env python3
import re
from pathlib import Path
from collections import defaultdict

def sanitize_name(name):
    return name.replace(".", "_").replace("-", "_")

def transform_tf_and_import(tf_file: Path, import_file: Path, output_tf: Path, output_import: Path):
    tf_text = tf_file.read_text()
    import_lines = import_file.read_text().splitlines()

    record_pattern = re.compile(
        r'resource "cloudflare_dns_record" "([^"]+)" {\s+(.*?)\s+}', re.DOTALL
    )

    resources = []
    key_to_resources = defaultdict(list)
    resource_name_map = {}

    for match in record_pattern.finditer(tf_text):
        old_resource_name = match.group(1)
        body = match.group(2)

        name_match = re.search(r'name\s+=\s+"([^"]+)"', body)
        type_match = re.search(r'type\s+=\s+"([^"]+)"', body)
        if not name_match or not type_match:
            continue

        fqdn = name_match.group(1)
        rtype = type_match.group(1)
        key = (fqdn, rtype)
        key_to_resources[key].append((old_resource_name, body.strip()))

    usage_counter = defaultdict(int)
    final_resources = []

    for (fqdn, rtype), blocks in key_to_resources.items():
        for idx, (old_name, body) in enumerate(blocks):
            base = f"{rtype}_{sanitize_name(fqdn)}"
            name = base if idx == 0 else f"{base}_{idx + 1}"
            resource_name_map[old_name] = name
            final_resources.append(f'resource "cloudflare_dns_record" "{name}" {{\n  {body}\n}}')

    # Rewrite import.sh
    final_import_lines = []
    for line in import_lines:
        match = re.match(r'terraform import cloudflare_dns_record\.([^\s]+)\s+(.+)', line)
        if match:
            old_name, record_id = match.groups()
            new_name = resource_name_map.get(old_name, old_name)
            final_import_lines.append(f"terraform import cloudflare_dns_record.{new_name} {record_id}")
        else:
            final_import_lines.append(line)

    output_tf.write_text("\n\n".join(final_resources))
    output_import.write_text("\n".join(final_import_lines))
    print(f"✅ Wrote canonized Terraform to {output_tf}")
    print(f"✅ Wrote canonized import script to {output_import}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        print("Usage: python3 cf-terraforming-canonizer.py <cf.tf> <import.sh>")
        sys.exit(1)

    tf_file = Path(sys.argv[1])
    import_file = Path(sys.argv[2])
    output_tf = Path("cf_canonized.tf")
    output_import = Path("import_canonized.sh")

    transform_tf_and_import(tf_file, import_file, output_tf, output_import)
