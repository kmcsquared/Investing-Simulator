"""Streamlit app to simulate investments over a period of time in the past"""

import datetime
import streamlit as st
from dateutil.relativedelta import relativedelta
import yfinance as yf
import pandas as pd
from currency_converter import CurrencyConverter

st.set_page_config(layout='wide')
st.title('Investing Simulator')
st.write('This app allows you to simulate how your investments would have developed over time if you had invested periodically in the past.')

today = datetime.datetime.now()
curr_conv = CurrencyConverter(fallback_on_missing_rate=True)

# Ask user to decide investment date range, as well as frequency and amount for investing
st.header('Choose frequency and amount of investments')

with st.form('input_date'):

    col_input_1, col_input_2, col_input_3 = st.columns(3)

    with col_input_1:

        date_start, date_end = st.date_input(
            label='Select the start and end dates for your periodic investments',
            value=(datetime.date(day=1, month=1, year=today.year), today),
            min_value=datetime.date(day=1, month=1, year=1970),
            max_value=today,
            format='DD/MM/YYYY'
        )

    with col_input_2:

        investment_day = st.selectbox(
            label='On which day of the month will you invest periodically?',
            options=range(1,29),
            index=0,
            help='Make sure the investment day falls in the selected date range.'
        )

    with col_input_3:

        investment_amount = st.number_input(
            label='How much will you invest periodically (in dollars)?',
            value=100,
            min_value=1
        )

    submitted = st.form_submit_button(label='CONFIRM CHOICES', use_container_width=True)
    if 'submitted' not in st.session_state:
        st.session_state['submitted'] = submitted

if st.session_state['submitted']:

    # Find correct start date
    IS_DATE_CORRECT = True

    # Same month
    is_same_month = date_start.month == date_end.month and date_start.year == date_end.year
    if is_same_month:
        # Investment day between start and end dates
        if date_start.day <= investment_day <= date_end.day:
            date_start = datetime.date(day=investment_day, month=date_start.month, year=date_start.year)
        else:
            # Investment day outside start and end dates (e.g. Investment day: 25, Date range: Jan 1-20)
            st.write('Please select a periodic investment day within the date range.')
            st.write(f'The periodic investment day ({investment_day}) is outside of the date range {date_start:%B} {date_start.day}-{date_end.day}')
            IS_DATE_CORRECT = False

    # Different month
    else:
        # e.g. Investment day: 25, Date range: Jan 20 - Feb _)
        if investment_day >= date_start.day:
            date_start = datetime.date(day=investment_day, month=date_start.month, year=date_start.year)
        # e.g. Investment day: 25, Date range: Jan 28 - Feb_
        else:
            if investment_day > date_end.day:
                # Investment day outside start and end days (e.g. Investment day: 25, Date range: Jan 28 - Feb 20)
                st.write('Please select a periodic investment day within the date range.')
                st.write(f'The periodic investment day ({investment_day}) is outside of the date range {date_start:%B} {date_start.day} - {date_end:%B} {date_end.day}')
                IS_DATE_CORRECT = False
            else:
                # Investment day outside start and end dates (e.g. Investment day: 25, Date range: Jan 28 - Feb 28)
                date_start += relativedelta(months=1)

    if IS_DATE_CORRECT:

        st.write(f'The first simulated investment will take place at the closest market open after {date_start:%B %d (%Y)}.')
        st.header('Choose your investments')

        input_ticker_symbol = st.text_input(
            label='Enter the ticker symbol(s) of your investment choice (separated by commas)',
            help='''
            A ticker symbol or stock symbol is an abbreviation used to uniquely identify publicly 
            traded shares of a particular stock or security on a particular stock exchange. 
            You can find these symbols at ***yahoofinance.com***. 

            (Examples) Symbol - Company:

            AAPL - Apple, Inc.

            MSFT - Microsoft Corporation

            TSLA - Tesla, Inc. 
            ''',
            placeholder='Example: AAPL, MSFT, TSLA'
        )

        symbol_data = {}
        tickers = {}
        symbols = []
        securities_invested = []

        if input_ticker_symbol != '':
            # Remove whitespaces and separate by commas
            ticker_symbols = input_ticker_symbol.replace(' ', '').split(',')
            # Remove duplicates and sort alphabetically
            ticker_symbols = sorted(set(ticker_symbols))

            for ts in ticker_symbols:
                ticker = yf.Ticker(ts)

                if len(ticker.info) == 1:
                    st.write(f'The ticker symbol {ticker} was not found.')
                else:
                    symbol = ticker.info['symbol']
                     
                    # Try to get security long name, otherwise short name, otherwise symbol
                    try:
                        security_name = f'{ticker.info['longName']} ({symbol})'
                    except KeyError:
                        try:
                            security_name = f'{ticker.info['shortName']} ({symbol})'
                        except KeyError:
                            security_name = symbol

                    if symbol not in tickers:
                        tickers[symbol] = ticker

                    symbols.append(symbol)
                    securities_invested.append(security_name)

            NUM_SECURITIES_INVESTED = len(securities_invested)
            if NUM_SECURITIES_INVESTED != 0:
                st.write(f'You will invest in the following {NUM_SECURITIES_INVESTED} {'security' if NUM_SECURITIES_INVESTED == 1 else 'securities'} on day {investment_day} of each month from {date_start:%B %d (%Y)} until {date_end:%B %d (%Y)}:')

                NUM_COLS = 4
                cols_securities = st.columns(NUM_COLS)
                for i, security in enumerate(securities_invested):
                    with cols_securities[i%NUM_COLS]:
                        st.write(f'{i+1}. {security}')

                # Create pandas DataFrame with columns:
                # Investment date, symbol, amount of shares bought, buy price
                rows = []
                current_investment_date = datetime.date(day=date_start.day, month=date_start.month, year=date_start.year)
                while current_investment_date <= date_end:
                    for symbol in sorted(symbols):
                        df_security = yf.download(
                            tickers=symbol,
                            start=current_investment_date - relativedelta(weeks=1),
                            end=current_investment_date + relativedelta(weeks=1)
                        )

                        # Create rows for DataFrame
                        row = []

                        # If market is closed, buy at next market open
                        if current_investment_date in df_security.index.date:
                            buy_price_original = df_security.loc[df_security.index.date == current_investment_date, 'Open'].iloc[0]
                            actual_investment_date = current_investment_date
                        else:
                            next_market_open_date = df_security.loc[df_security.index.date > current_investment_date].index[0]
                            buy_price_original = df_security.loc[df_security.index == next_market_open_date, 'Open'].iloc[0]
                            actual_investment_date = next_market_open_date.date()

                        # Convert security currency to USD
                        currency_security = tickers[symbol].info['currency']

                        if currency_security == 'USD':
                            buy_price_converted = buy_price_original
                        else:
                            buy_price_converted = curr_conv.convert(
                                amount=buy_price_original,
                                currency=currency_security,
                                new_currency='USD',
                                date=actual_investment_date,
                            )

                        # Allow for fractional shares if buy price is bigger
                        num_shares_bought = investment_amount / buy_price_converted
                        row += [
                            actual_investment_date, symbol, currency_security, num_shares_bought, 
                            buy_price_original, buy_price_converted, investment_amount
                        ]
                        rows.append(row)

                    current_investment_date += relativedelta(months=1)
                    if current_investment_date > date_end:
                        break

            df_investments = pd.DataFrame(
                data=rows,
                columns=['Buy Date', 'Symbol', 'Original Currency', 'Shares Bought', 'Share Price (Original Currency)', 'Share Price (USD)', 'Invested Capital (USD)']
            )

            st.header('Transactions')
            st.dataframe(df_investments, use_container_width=True)
