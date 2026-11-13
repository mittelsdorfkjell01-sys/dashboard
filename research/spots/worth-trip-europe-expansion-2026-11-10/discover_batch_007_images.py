"""Independent Commons/Openverse image discovery for blind batch 007."""
from discover_batch_002_images import commons, openverse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parent
SPOTS=[
 ("Torbole","Torbole Lake Garda windsurf"),("Malcesine","Malcesine Lake Garda windsurf"),("Campione del Garda","Campione del Garda kitesurf"),
 ("Dervio","Dervio Lake Como windsurf"),("Colico","Colico Lake Como kitesurf"),("Gera Lario","Gera Lario windsurf"),("Valmadrera","Valmadrera Lake Como windsurf"),("Cannobio","Cannobio Lake Maggiore windsurf"),
 ("Grado Pineta","Grado Pineta kitesurf"),("Marina Julia","Marina Julia windsurf"),("Sottomarina","Sottomarina kitesurf"),("Porto Corsini","Porto Corsini kitesurf"),
 ("Senigallia","Senigallia windsurf surf"),("Porto Recanati","Porto Recanati kitesurf"),("Vieste","Vieste kitesurf windsurf"),("Torre Guaceto","Torre Guaceto kitesurf"),
 ("Porto Cesareo","Porto Cesareo kitesurf"),("Gallipoli","Gallipoli Puglia kitesurf"),("Talamone","Talamone windsurf kitesurf"),("Castiglione della Pescaia","Castiglione della Pescaia windsurf"),
 ("Santa Marinella","Santa Marinella surf Italy"),("Lido di Ostia","Ostia surf kitesurf"),("Mondello","Mondello windsurf Palermo"),("Puzziteddu","Puzziteddu kitesurf windsurf"),("Pozzallo","Pozzallo kitesurf")]

def discover(row):
 name,q=row; providers={}; errors=[]
 for pn,fn in (("wikimedia_commons",commons),("openverse",openverse)):
  try: providers[pn]=fn(q)
  except Exception as exc: providers[pn]=[]; errors.append(f"{pn}: {type(exc).__name__}")
 return {"spot":name,"query":q,"providers":providers,"errors":errors,"review_status":"unreviewed_candidates_not_approved"}

if __name__=="__main__":
 with ThreadPoolExecutor(max_workers=10) as pool: rows=list(pool.map(discover,SPOTS))
 payload={"generated_at":datetime.now(timezone.utc).isoformat(),"independence_statement":"Created before local/database comparison for batch 007.","limitations":["Search relevance is not geographic proof.","Every candidate requires visual, geographic, resolution and licence review."],"spots":rows}
 (ROOT/"batch-007-blind-image-candidates.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
