"""Fetch regional observed weather; never substitute forecasts for rainfall records."""
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request,urlopen

ROOT=Path(__file__).resolve().parent
SOURCES={
    'noaa_awc':'https://aviationweather.gov/api/data/metar?ids=SKPE&hours=24&format=json',
    'iem_history':'https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?station=SKPE&data=metar&year1=2026&month1=10&day1=14&year2=2026&month2=10&day2=15&tz=Etc%2FUTC&format=onlycomma&latlon=no&elev=no&missing=M&trace=T&direct=no&report_type=3&report_type=4'
}
def fetch(item):
    key,url=item
    try:
        with urlopen(Request(url,headers={'User-Agent':'OKUA-maintenance-weather-context/1.0'}),timeout=18) as response:
            raw=response.read(2_000_000).decode('utf-8',errors='replace')
        (ROOT/f'weather_{key}_raw.txt').write_text(raw,encoding='utf-8')
        if key=='noaa_awc':
            rows=json.loads(raw)
            usable=[r for r in rows if str(r.get('reportTime','')).startswith('2026-10-14')]
            preview=[{k:r.get(k) for k in ('reportTime','rawOb','temp','dewp','wxString','lat','lon')} for r in usable]
        else:
            preview=[line for line in raw.splitlines() if line.startswith('SKPE,2026-10-14')]
            usable=preview
        return {'source':key,'url':url,'fetch_status':'success','date_matched_rows':len(usable),'observations':preview,
                'raw_file':f'weather_{key}_raw.txt'}
    except Exception as error:
        return {'source':key,'url':url,'fetch_status':'error','error':str(error)[:300]}

with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(fetch,SOURCES.items()))
out={
    'retrieved_at_utc':datetime.now(timezone.utc).isoformat(),
    'study_date':'2026-10-14','study_timezone':'America/Bogota',
    'station':'SKPE / Aeropuerto Matecaña, Pereira',
    'local_site':'Bioparque Ukumarí, Caja 5',
    'spatial_limit':'Airport observation is regional context, not a measured rainfall record at Caja 5.',
    'trials_so_far_local':'12:40 through 13:38; UTC = local + 5 h',
    'operator_observation':{'surface':'synthetic_grass','moisture':'slightly_damp'},
    'rain_before_during_after_trials':'unverified_pending_timestamped_observation_review',
    'sources':results,
    'forecast_search_result':{'url':'https://www.theweathernetwork.com/en/airport/co/risaralda/pereira-matecana/14-days',
                            'date':'2026-10-14','type':'forecast_only',
                            'rain_probability_day_pct':60,'forecast_rain_mm':'1-3',
                            'restriction':'Not evidence that rain actually occurred before, during or after trials.'}
}
(ROOT/'weather_context.json').write_text(json.dumps(out,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps({'retrieved_at_utc':out['retrieved_at_utc'],'sources':results},ensure_ascii=False))
