#----------------------------------------------------------------------------#
# Imports
#----------------------------------------------------------------------------#
import os
import sys
import json
import time
import datetime
import pandas as pd
import requests
from flask import Flask, render_template, request, Response, flash, redirect, url_for, jsonify, abort
#----------------------------------------------------------------------------#
# App Config.
#----------------------------------------------------------------------------#

app = Flask(__name__)

#----------------------------------------------------------------------------#
# Filters.
#----------------------------------------------------------------------------#

def parse_price(row):
    if (pd.isna(row['price_details']) or 'price_usd' not in row['price_details']):
        return 'nan'
    else:
        return row['price_details']['price_usd']

def parse_contract(row):
    if (pd.isna(row['contract_address'])):
        return row['nft']['contract_address']
    else:
        return row['contract_address']

def parse_tokenid(row):
    if (pd.isna(row['token_id'])):
        return row['nft']['token_id']
    else:
        return row['token_id']

def parse_caption(row, address):
    if (row['name'] != '???'):
        n = row['name']
    else:
        n = '#'+row['token_id']

    if (row['type']=='mint'):
        return 'Minted '+n
    elif (row['type']=='transfer' and row['transfer_to']== address.lower()):
        return 'Received '+n
    elif (row['type']=='transfer'):
        return 'Sent '+n
    elif (row['type']=='sale' and row['buyer_address']== address.lower()):
        return 'Bought '+n
    else:
        return 'Sold '+n

def format_date(value):
    date_obj = datetime.strptime(value, '%Y-%m-%dT%H:%M:%S')
    return date_obj.strftime("%d/%m/%Y at %H:%M:%S")

def parse_date(row):
    return format_date(row['transaction_date'])

def process_json(data, address):
    data_json = data['transactions']
    df = pd.DataFrame(data_json)
    df['contract_address'] = df.apply(lambda row: parse_contract(row), axis=1)
    df['token_id'] = df.apply(lambda row: parse_tokenid(row), axis=1)

    if 'price_details' in df:
        df['price'] = df.apply(lambda row: parse_price(row), axis=1)
    else:
        df['price'] = 0

    if 'buyer_address' not in df:
        df['buyer_address'] = '0'
        df['seller_address'] = '0'

    if 'transfer_to' not in df:
        df['transfer_to'] = '0'
        df['transfer_from'] = '0'

    df = df[['type', 'transaction_date', 'transfer_to', 'transfer_from', 'buyer_address', 'seller_address', 'price', 'contract_address', 'token_id']]
    df = df[(df['type'] == 'sale') | (df['type'] == 'mint') | (df['type'] == 'transfer')]

    df['link'] = 'static/img/istockphoto-1278906674-170667a.jpg'
    OPENSEA_API_KEY=os.environ.get("SEA_KEY")
    HEAD = {"X-API-KEY": OPENSEA_API_KEY, "Accept": "application/json", "User-Agent": "Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:47.0) Gecko/20100101 Firefox/47.0"}
    for index, row in df.iterrows():
        URL = 'https://api.opensea.io/api/v1/asset/'+row['contract_address']+'/'+row['token_id']+'/'
        r = requests.get(url = URL, headers = HEAD)
        result = r.json()
        if 'image_thumbnail_url' in result:
            df.loc[index, 'link'] = result['image_thumbnail_url']
        else:
            df.loc[index, 'link'] = 'static/img/istockphoto-1278906674-170667a.jpg'
        if ('name' in result) and (result['name'] is not None):
            df.loc[index, 'name'] = result['name']
        else:
            df.loc[index, 'name'] = '???'

    df['caption'] = df.apply(lambda row: parse_caption(row, address), axis=1)
    return df

def call_nftport(address, continuation):
    NFTPORT_API_KEY=os.environ.get("PORT_KEY")
    HEAD = {'Authorization': NFTPORT_API_KEY, 'Content-Type': 'application/json'}

    if continuation != 0:
        URL = 'https://api.nftport.xyz/v0/transactions/accounts/'+address+'?chain=ethereum&type=mint&type=sell&type=buy&type=transfer_to&type=transfer_from&continuation='+continuation
    else:
        URL = 'https://api.nftport.xyz/v0/transactions/accounts/'+address+'?chain=ethereum&type=mint&type=sell&type=buy&type=transfer_to&type=transfer_from'

    r = requests.get(url = URL, headers = HEAD)
    data = r.json()
    return data

#----------------------------------------------------------------------------#
# Controllers.
#----------------------------------------------------------------------------#

@app.route('/')
def index():
    return render_template('pages/index.html', results = {"success": 'True', "data": {}, "count": 0, "address": 0, "continuation": 0})


@app.route('/data')
def data():
    address = request.args.get('address')

    print("Returning first page")
    data = call_nftport(address, 0)

    if data['response'] == 'OK':
        df = process_json(data, address)
        success = 'True'
        if('continuation' in data):
            continuation = data['continuation']
            return render_template('pages/index3.html', results = {"success": success, "data": df, "count": len(df), "address": address, "continuation": continuation})
        else:
            return render_template('pages/index3.html', results = {"success": success, "data": df, "count": len(df), "address": address, "continuation": 'x'})
    else:
        df = []
        success = 'False'
        return render_template('pages/index3.html', results = {"success": success, "data": df, "count": len(df), "address": address, "continuation": 'x'})


@app.route('/cont')
def cont():
    address = request.args.get('address')
    continuation = request.args.get('c')

    if continuation == 'x':
        jsonDf = {}
        success = 'True'
        return {"success": success, "data": jsonDf, "count": len(jsonDf), "address": address, "continuation": 'xxx'}
    else:
        print(f"Returning page {continuation}")
        data = call_nftport(address, continuation)
        df = process_json(data, address)
        success = 'True'

        if len(df.index) < 50:
            print("Returning last page")
        jsonDf = df.to_json(orient='index')
        continuation = data['continuation']
        return {"success": success, "data": jsonDf, "count": len(jsonDf), "address": address, "continuation": continuation}


#Todo:clean up all useless garbage
#change colour of box and shadow
#Todo: deploy
#Todo: chat to developer dao, furqhan and nftport
#todo: tweet about it


@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def server_error(error):
    return render_template('errors/500.html'), 500

#----------------------------------------------------------------------------#
# Launch.
#----------------------------------------------------------------------------#

# Default port:
if __name__ == '__main__':
    app.run()

# Or specify port manually:
'''
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
'''
