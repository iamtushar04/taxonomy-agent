import os

file_path = r'c:\Users\Vipul\Desktop\taxonomies_agent\web_app\backend\routes\taxonomy_routes.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the line
old_str = 'filename=f"Taxonomy_Matrix_{run_id}.xlsx",'
new_str = 'filename=f"{run_record.name.replace(\' \', \'_\')}.xlsx" if run_record.name else f"Taxonomy_Matrix_{run_id}.xlsx",\n        headers={"Access-Control-Expose-Headers": "Content-Disposition"},'

if old_str in content:
    content = content.replace(old_str, new_str)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Success")
else:
    print("Target not found")
