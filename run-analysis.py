import os
import dotenv
import requests
import pandas as pd
import numpy as np
from pprint import pprint
from tqdm import tqdm
import time
import pickle

dotenv.load_dotenv()
API_KEY = os.environ['API_KEY']

df = pd.read_excel('./data/Childcare_provider_level_data_as_at_31_March_2018.ods', 'Childcare_providers')
eyr_df = df.loc[df['Individual Register Combinations'] == 'EYR Only']
eyr_df = eyr_df.loc[eyr_df['Provider Postcode'] != 'Redacted']
bin_df = pd.read_csv('./data/chidcare_providers_eyr_clean.csv')

url = 'https://api.os.uk/search/match/v1/match'

params = {
    'minmatch': 0.5,
    'key': API_KEY,
    'matchprecision': 3,
    'dataset': 'LPI,DPA'
}

class Provider():
    def __init__(self, row):
        self.urn = row['Provider URN']
        self.name = row['Provider Name']
        self.address1 = row['Provider Address 1']
        self.address2 = row['Provider Address 2']
        self.address3 = row['Provider Address 3']
        self.postcode = row['Provider Postcode']
        self.results = self.get_data()

    def call_api(self, address, label):
        results = []
        params['query'] = address
        try:
            data = requests.get(url, params=params).json()
            if data['header']['totalresults'] > 0:
                for i, result in enumerate(data['results']):
                    if 'DPA' in result:
                        uprn = result['DPA']['UPRN']
                        match = result['DPA']['MATCH']
                        postcode = result['DPA']['POSTCODE']
                        results.append({
                            'label': label,
                            'uprn': uprn,
                            'match': match,
                            'dataset': 'DPA',
                            'postcode': postcode,
                            'coord_accuracy': None,
                            'x': result['DPA']['X_COORDINATE'],
                            'y': result['DPA']['Y_COORDINATE']
                        })
                    elif 'LPI' in result:
                        uprn = result['LPI']['UPRN']
                        match = result['LPI']['MATCH']
                        postcode = result['LPI']['POSTCODE_LOCATOR']
                        results.append({
                            'label': label,
                            'uprn': uprn,
                            'match': match,
                            'dataset': 'LPI',
                            'postcode': postcode,
                            'coord_accuracy': result['LPI']['RPC'],
                            'x': result['LPI']['X_COORDINATE'],
                            'y': result['LPI']['Y_COORDINATE']
                        })
            else:
                results.append({
                    'label': label,
                    'uprn': np.nan
                })
        except Exception as e:
            print(e)
            results.append({
                'label': label,
                'uprn': -999
            })
        time.sleep(0.2)
        return results

    def get_data(self):
        results = []
        for label in ['name_full_postcode', 'no_name_full_postcode']:
            address_components = []
            if label == 'name_full_postcode':
                address_components.append(self.name)
            for address_component in [self.address1, self.address2, self.address3, self.postcode]:
                if address_component and address_component != 'NR':
                    address_components.append(str(address_component))
            address = ', '.join(address_components)
            results.extend(self.call_api(address, label))
        return results
            
providers = []

for idx, (_, row) in tqdm(enumerate(eyr_df.iterrows())):
    providers.append(Provider(row))
    if idx % 100 == 0 or idx == len(eyr_df) - 1:
        with open('./data/providers.pkl', 'wb') as f:
            pickle.dump(providers, f)

rows = []
for provider in providers:
    for result in provider.results:
        row = {
            'urn': provider.urn,
            'name': provider.name,
            'provider_postcode': provider.postcode
        }
        for key in ['label', 'uprn', 'match', 'dataset', 'postcode', 'coord_accuracy', 'x', 'y']:
            if key in result:
                row[key] = result[key]
        rows.append(row)
results_df = pd.DataFrame(rows)

output_dfs = []
for urn in results_df['urn'].unique():
    tmp_df = results_df.loc[results_df['urn'] == urn]
    tmp_df = tmp_df.loc[tmp_df['match'] == tmp_df['match'].max()].drop_duplicates(['uprn', 'postcode'])
    output_dfs.append(tmp_df)
output_df = pd.concat(output_dfs)

output_df.to_csv('output.csv', index=False)
