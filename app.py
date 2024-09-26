from flask import Flask, render_template, request, redirect, url_for
from pymongo import MongoClient
import requests
import os
from urllib.parse import quote_plus
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# Escape special characters in username and password
username = quote_plus(os.getenv("MONGO_USERNAME"))
password = quote_plus(os.getenv("MONGO_PASSWORD"))

# MongoDB setup
MONGO_URI = f"mongodb+srv://{username}:{password}@{os.getenv('MONGO_HOST')}/?retryWrites=true&w=majority&ssl=true&tlsAllowInvalidCertificates=true"
client = MongoClient(MONGO_URI)
db = client[os.getenv('MONGO_DB')]  # Database name
portfolio_collection = db[os.getenv('MONGO_COLLECTION')]  # Collection name

# Finnhub API Key (replace with your API key)
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")

@app.route('/')
def dashboard():
    # Fetch all stocks from MongoDB
    portfolio = list(portfolio_collection.find())
    total_value, total_profit_loss = update_portfolio(portfolio)
    return render_template('dashboard.html', portfolio=portfolio,
                           total_value=total_value, total_profit_loss=total_profit_loss)

@app.route('/buy', methods=['GET', 'POST'])
def buy_stock():
    if request.method == 'POST':
        symbol = request.form['symbol'].upper()
        quantity = int(request.form['quantity'])
        stock_price = get_stock_price(symbol)
        if stock_price:
            # Check if stock already exists in portfolio
            if portfolio_collection.find_one({'symbol': symbol}):
                error = 'You already own this stock.'
                return render_template('buy.html', error=error)

            # Add new stock to MongoDB
            new_stock = {
                'symbol': symbol,
                'buy_price': stock_price,
                'total_shares': quantity
            }
            portfolio_collection.insert_one(new_stock)
            return redirect(url_for('dashboard'))
        else:
            error = 'Invalid NASDAQ Symbol'
            return render_template('buy.html', error=error)
    return render_template('buy.html')

@app.route('/sell/<symbol>', methods=['GET', 'POST'])
def sell_stock(symbol):
    stock = portfolio_collection.find_one({'symbol': symbol})
    if stock:
        if request.method == 'POST':
            quantity_to_sell = int(request.form['quantity'])
            if quantity_to_sell <= stock['total_shares']:
                new_quantity = stock['total_shares'] - quantity_to_sell
                if new_quantity == 0:
                    portfolio_collection.delete_one({'symbol': symbol})
                else:
                    portfolio_collection.update_one({'symbol': symbol}, {'$set': {'total_shares': new_quantity}})
            return redirect(url_for('dashboard'))
        return render_template('sell.html', symbol=symbol, stock=stock)
    else:
        return redirect(url_for('dashboard'))

def get_stock_price(symbol):
    url = f'https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB_API_KEY}'
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        if data.get('c'):
            return data['c']  # 'c' is the current price
    return None

def update_portfolio(portfolio):
    total_value = 0
    total_profit_loss = 0
    for stock in portfolio:
        current_price = get_stock_price(stock['symbol'])
        if current_price:
            stock['current_value'] = current_price
            profit_loss = (current_price - stock['buy_price']) * stock['total_shares']
            stock['profit_loss'] = profit_loss
            total_value += current_price * stock['total_shares']
            total_profit_loss += profit_loss
        else:
            stock['current_value'] = 'N/A'
            stock['profit_loss'] = 'N/A'
    return total_value, total_profit_loss

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5001)))
