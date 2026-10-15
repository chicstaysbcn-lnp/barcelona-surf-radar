import sys
import unittest
from pathlib import Path
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))
from forecast import SPOTS, MODELS, PROFILE_DATA, circular_mean, circular_distance, score_hour, fold_hour, iso_utc, open_meteo_fetch, forecast_spot, spot_fit
from alerts import choose_alert, sessions

BASE = {
    'wave_m': .95, 'period_s': 8, 'swell_m': .72, 'swell_dir': 120,
    'wave_dir': 120, 'wind_kn': 3, 'wind_dir': 300, 'gust_kn': 5,
    'is_day': True, 'weather_code': 0, 'wave_spread_m': .12,
    'marine_n': 4, 'weather_n': 3,
}

class ForecastTest(unittest.TestCase):
    def test_open_meteo_parser_and_utc(self):
        model = MODELS[0]
        api_response = {'hourly': {'time': ['2026-10-14T08:00','2026-10-14T09:00'],
                                   'wind_speed_10m': [2.5,4.0], 'is_day': [1,1]}}
        with patch('forecast.get_json', return_value=api_response) as mocked:
            kind, name, result = open_meteo_fetch(SPOTS[0], model)
        self.assertEqual(kind, 'weather')
        self.assertIn('2026-10-14T08:00:00Z', result)
        self.assertEqual(result['2026-10-14T09:00:00Z']['wind_speed_10m'],4.0)
        self.assertEqual(mocked.call_args.args[1]['models'], 'arome_france')

    def test_end_to_end_aggregation_with_fake_apis(self):
        now=datetime(2026,10,14,8,tzinfo=timezone.utc)
        hourly_times=['2026-10-14T10:00','2026-10-14T11:00','2026-10-14T12:00']
        def fake_get(url, params=None, payload=None, retries=1):
            if '/marine' in url:
                if params['models']=='best_match':
                    return {'hourly':{'time':hourly_times, 'sea_level_height_msl':[.11,.12,.13],
                                      'sea_surface_temperature':[20.1,20.1,20.2]}}
                return {'hourly':{'time':hourly_times,'wave_height':[.9,1.1,1.0],
                                  'wave_period':[7,8,8], 'wave_direction':[120,120,120],
                                  'swell_wave_height':[.7,.8,.8], 'swell_wave_direction':[120,120,120],
                                  'swell_wave_period':[8,8,8]}}
            return {'hourly':{'time':hourly_times,'wind_speed_10m':[4,4,4],
                              'wind_direction_10m':[300,300,300], 'wind_gusts_10m':[6,6,6],
                              'temperature_2m':[22,22,22], 'weather_code':[1,1,1], 'is_day':[1,1,1]}}
        with patch('forecast.get_json', side_effect=fake_get), patch.dict('os.environ',{'WINDY_API_KEY':''}):
            spot=forecast_spot(SPOTS[2],now)
        self.assertEqual(len(spot['hours']),3)
        self.assertEqual(spot['hours'][0]['marine_n'],4)
        self.assertEqual(spot['hours'][0]['weather_n'],3)
        self.assertIn('AROME (Météo-France)',spot['source_names'])
        self.assertIn('ECMWF WAM',spot['source_names'])
        self.assertGreater(spot['hours'][1]['scores']['intermedio'],70)

    def test_circular_direction_near_north(self):
        self.assertTrue(circular_mean([350, 10]) < 25 or circular_mean([350, 10]) > 335)
        self.assertEqual(circular_distance(350, 10), 20)

    def test_fair_surf_score(self):
        good = score_hour(SPOTS[2], BASE)
        self.assertGreaterEqual(good, 70)
        self.assertLessEqual(good, 100)

    def test_no_surf_in_flat_water(self):
        flat = BASE | {'wave_m': .12, 'period_s': 3.2}
        self.assertLessEqual(score_hour(SPOTS[2], flat), 46)

    def test_no_surf_in_storm(self):
        storm = BASE | {'gust_kn': 36, 'weather_code': 95}
        self.assertLessEqual(score_hour(SPOTS[2], storm), 22)

    def test_missing_model_data(self):
        self.assertEqual(score_hour(SPOTS[2], BASE | {'marine_n': 0, 'wave_m': None}), 0)
        self.assertEqual(score_hour(SPOTS[2], BASE | {'weather_n': 0}), 0)

    def test_night_is_never_recommended(self):
        self.assertEqual(score_hour(SPOTS[2], BASE | {'is_day': False}), 0)

    def test_divergence_penalizes_score(self):
        self.assertLess(score_hour(SPOTS[2], BASE | {'wave_spread_m': .8}), score_hour(SPOTS[2], BASE))

    def test_time_parsing_in_utc(self):
        self.assertEqual(iso_utc('2026-10-14T11:00Z'), '2026-10-14T11:00:00Z')

    def test_model_folding(self):
        t='2026-10-14T11:00:00Z'
        inputs=[
            ('marine', 'M1', {t:{'wave_height':.8,'wave_period':7,'wave_direction':115,'swell_wave_height':.6,'swell_wave_direction':115}}),
            ('marine', 'M2', {t:{'wave_height':1.0,'wave_period':8,'wave_direction':125,'swell_wave_height':.7,'swell_wave_direction':125}}),
            ('weather','W1',{t:{'wind_speed_10m':5,'wind_direction_10m':305,'temperature_2m':23,'is_day':1}}),
            ('sea','S',{t:{'sea_level_height_msl':.12,'sea_surface_temperature':21.4}}),
        ]
        h=fold_hour(t,inputs,SPOTS[2])
        self.assertEqual(h['marine_n'],2)
        self.assertEqual(h['weather_n'],1)
        self.assertEqual(h['wave_m'],.9)
        self.assertAlmostEqual(h['wave_spread_m'],.2)
        self.assertEqual(h['sea_level_m'],.12)
        self.assertEqual(h['sea_temp_c'],21.4)
        self.assertEqual(h['is_day'],True)

    def test_seven_profiles_and_separate_mar_bella(self):
        self.assertEqual(len(SPOTS),7)
        self.assertEqual(len({spot['id'] for spot in SPOTS}),7)
        self.assertNotIn('nova-mar-bella',{spot['id'] for spot in SPOTS})
        self.assertEqual(len([s for s in PROFILE_DATA['spots'] if s['classification']=='provisional']),3)

    def test_individual_swell_orientation_changes_ranking(self):
        sant=next(s for s in SPOTS if s['id']=='sant-sebastia')
        mar=next(s for s in SPOTS if s['id']=='mar-bella')
        data=BASE | {'wind_kn': 1.0, 'wind_dir': 270, 'wave_m': 1.0,
                     'period_s': 7.5, 'swell_m': .85}
        east=data|{'swell_dir':90, 'wave_dir':90}
        southeast=data|{'swell_dir':135, 'wave_dir':135}
        self.assertGreater(score_hour(sant,east),score_hour(mar,east))
        self.assertGreater(score_hour(mar,southeast),score_hour(sant,southeast))

    def test_tide_unvalidated_is_informational_only(self):
        sant=next(s for s in SPOTS if s['id']=='sant-sebastia')
        self.assertEqual(score_hour(sant, BASE | {'sea_level_m':.6}),
                         score_hour(sant, BASE | {'sea_level_m':-.3}))

    def test_per_spot_fit_labels(self):
        mar=next(s for s in SPOTS if s['id']=='mar-bella')
        self.assertEqual(spot_fit(mar,135,315,7),('favorable','offshore probable'))
        self.assertEqual(spot_fit(mar,260,135,12),('desfavorable','onshore probable'))

    def test_notifications_require_two_good_daylight_hours(self):
        now=datetime(2026,10,14,8,tzinfo=timezone.utc)
        start=now+timedelta(hours=3)
        hours=[]
        for i in range(2):
            hours.append({
              'time':(start+timedelta(hours=i)).isoformat().replace('+00:00','Z'),
              'is_day':True,'danger':False,'marine_n':3,'weather_n':2,
              'wave_m':1,'period_s':8,'wind_kn':3,
              'scores':{'intermedio':88}
            })
        snapshot={'spots':[{'name':'Barceloneta','id':'barceloneta','hours':hours}]}
        picked=choose_alert(snapshot,{'sent':{}},threshold=76,now=now)
        self.assertIsNotNone(picked)
        self.assertEqual(picked['score'],88)
        self.assertIsNone(choose_alert(snapshot,{'sent':{picked['date']:{}}},threshold=76,now=now))
        snapshot['spots'][0]['hours'][1]['is_day']=False
        self.assertIsNone(choose_alert(snapshot,{'sent':{}},threshold=76,now=now))

    def test_alert_source_count_restriction(self):
        now=datetime(2026,10,14,8,tzinfo=timezone.utc)
        hours=[]
        for i in range(2):
            hours.append({'time':(now+timedelta(hours=i+2)).isoformat().replace('+00:00','Z'),
                          'is_day':True,'danger':False,'marine_n':1,'weather_n':2,'scores':{'intermedio':90}})
        self.assertEqual(sessions({'spots':[{'name':'Bogatell','id':'bogatell','hours':hours}]},now=now),[])

if __name__=='__main__':unittest.main()
