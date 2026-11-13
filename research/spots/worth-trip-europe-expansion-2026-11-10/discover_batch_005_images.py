"""Independent Commons/Openverse image discovery for blind batch 005."""
from discover_batch_002_images import commons, openverse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parent
SPOTS=[
("Lancieux","Lancieux kitesurf"),("Saint-Brevin Rochelets","Saint Brevin Rochelets kitesurf"),("La Baule","La Baule kitesurf"),("Les Sables d'Olonne","Les Sables d'Olonne surf"),("Pontaillac","Pontaillac surf"),("Hourtin Lake","Hourtin Lake kitesurf"),("Biscarrosse Plage","Biscarrosse surf"),("Gruissan Chalets","Gruissan Chalets kitesurf"),("Almanarre","Almanarre kitesurf"),("Leucate La Franqui","Leucate La Franqui kitesurf"),("Pantin","Pantin Galicia surf"),("Patos","Patos Galicia surf"),("Somo","Somo Cantabria surf"),("Salinas Asturias","Salinas Asturias surf"),("Trabucador","Trabucador kitesurf"),("Castelldefels La Pineda","Castelldefels kitesurf"),("El Palmar","El Palmar Cadiz surf"),("Mar Menor La Mota","Mar Menor La Mota windsurf"),("Cape Drepano","Cape Drepano kitesurf"),("Raches Lighthouse","Raches Greece kitesurf"),("Vassiliki","Vassiliki windsurf"),("Nea Kios","Nea Kios kitesurf"),("Ai Giannis Lefkada","Ai Giannis Lefkada kitesurf"),("Prasonisi","Prasonisi windsurf"),("Karpathos Afiartis","Karpathos Afiartis windsurf")]
def discover(row):
 name,q=row; providers={}; errors=[]
 for pn,fn in (("wikimedia_commons",commons),("openverse",openverse)):
  try: providers[pn]=fn(q)
  except Exception as exc: providers[pn]=[]; errors.append(f"{pn}: {type(exc).__name__}")
 return {"spot":name,"query":q,"providers":providers,"errors":errors,"review_status":"unreviewed_candidates_not_approved"}
if __name__=="__main__":
 with ThreadPoolExecutor(max_workers=10) as pool: rows=list(pool.map(discover,SPOTS))
 payload={"generated_at":datetime.now(timezone.utc).isoformat(),"independence_statement":"Created before local/database comparison for batch 005.","limitations":["Search relevance is not geographic proof.","Every candidate requires visual, geographic, resolution and licence review."],"spots":rows}
 (ROOT/"batch-005-blind-image-candidates.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
