"""Independent Commons/Openverse image discovery for blind batch 008."""
from discover_batch_002_images import commons, openverse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parent
SPOTS=[("Portoroz Seca","Portoroz Seca Slovenia windsurf"),("Izola","Izola Slovenia windsurf"),("Koper Zusterna","Koper Zusterna windsurf"),("Strunjan","Strunjan Slovenia windsurf"),("Lake Bohinj","Lake Bohinj windsurf"),
 ("Punat Krk","Punat Krk windsurf"),("Baska Krk","Baska Krk windsurf"),("Nin Zdrijac","Nin Zdrijac kitesurf"),("Sabunike","Sabunike kitesurf"),("Privlaka","Privlaka Croatia kitesurf"),("Jadrija","Jadrija windsurf"),("Zaton Sibenik","Zaton Sibenik windsurf"),("Omis Duce","Omis Duce windsurf kitesurf"),("Bacvice Split","Bacvice Split windsurf"),("Kuciste Peljesac","Kuciste Peljesac windsurf"),
 ("Neum","Neum Bosnia windsurf"),("Tivat Bay","Tivat Montenegro windsurf"),("Kotor Bay Orahovac","Kotor Bay Orahovac windsurf"),("Lake Skadar Vranjina","Lake Skadar windsurf"),
 ("Vlore Narta","Vlore Narta Lagoon kitesurf"),("Durres Golem","Durres Golem kitesurf"),("Lalzit Bay","Lalzit Bay kitesurf"),("Lake Shkodra Shiroka","Lake Shkodra Shiroka windsurf"),
 ("Struga Lake Ohrid","Struga Lake Ohrid windsurf"),("Lake Prespa Stenje","Lake Prespa Stenje windsurf")]
def discover(row):
 name,q=row; providers={}; errors=[]
 for pn,fn in (("wikimedia_commons",commons),("openverse",openverse)):
  try: providers[pn]=fn(q)
  except Exception as exc: providers[pn]=[]; errors.append(f"{pn}: {type(exc).__name__}")
 return {"spot":name,"query":q,"providers":providers,"errors":errors,"review_status":"unreviewed_candidates_not_approved"}
if __name__=="__main__":
 with ThreadPoolExecutor(max_workers=10) as pool: rows=list(pool.map(discover,SPOTS))
 payload={"generated_at":datetime.now(timezone.utc).isoformat(),"independence_statement":"Created before local/database comparison for batch 008.","limitations":["Search relevance is not geographic proof.","Every candidate requires visual, geographic, resolution and licence review."],"spots":rows}
 (ROOT/"batch-008-blind-image-candidates.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
