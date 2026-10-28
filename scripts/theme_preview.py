"""Generate the real page fixtures used to check both appearances offline."""
import subprocess
import sys
for script in ('management','ads_overview','sales_theme','costs_theme','promotions_theme','promotion_participation_theme','crm_home','kyra','freight_audit','anuncios_progress','full_report'):
    subprocess.run([sys.executable, 'scripts/'+script+'_preview.py'], check=True)
