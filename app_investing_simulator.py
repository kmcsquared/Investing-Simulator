"""Streamlit app to simulate investments over a period of time in the past"""

import datetime
import pandas as pd
import streamlit as st
import yfinance as yf
import plotly.express as px
import cpi
import helper

st.set_page_config(layout='wide')
st.title('Investing Simulator (Dollar-Cost Averaging)')
st.write(
    '''
    - This app allows you to simulate how your investments would have performed over time 
    if you had invested on a periodic basis, inspired by the [dollar-cost averaging](
    https://www.investopedia.com/terms/d/dollarcostaveraging.asp) strategy.

    - The simulation assumes that it is possible to buy fractional shares
    and that there are no currency exchange fees.

    - If the scheduled investment happens on a day when the stock market 
    is closed, the buy order will be executed in the next market opening.
    
    - Orders are executed at market open by default and are compared against
    market close prices for each date.
    '''
)

today = datetime.datetime.now()
currencies = sorted(helper.curr_conv.currencies)

st.header('Choose your investment strategy', divider='rainbow')
# Ask user to decide investment date range, as well as frequency and amount for investing
with st.form('input_investment_parameters'):

    col_input_1, col_input_2, col_input_3, col_input_4 = st.columns(4)

    with col_input_1:
        date_start, date_end = st.date_input(
            label='In what date range will you be investing?',
            value=(datetime.date(day=1, month=1, year=today.year), today),
            min_value=datetime.date(day=1, month=1, year=1970),
            max_value=today,
            format='DD/MM/YYYY'
        )

    with col_input_2:
        investment_frequency = st.selectbox(
            label='How often will you invest?',
            options=['Daily', 'Weekly', 'Monthly'],
            index=2,
        )

    with col_input_3:
        investment_amount = st.number_input(
            label='How much will you invest periodically?',
            min_value=1,
            value=100,
            step=50
        )

    with col_input_4:
        base_currency = st.selectbox(
            label='Select your base currency.',
            options=currencies,
            index=currencies.index('USD'),
            help='''
            If the security is traded in a currency that is not your base currency, 
            a currency exchange will occur.
            '''
        )

    input_ticker_symbol = st.text_input(
        label='Enter the ticker symbol(s) of your investment choice (separated by commas)',
        help='''
        A ticker symbol or stock symbol is an abbreviation used to uniquely identify publicly 
        traded shares of a particular stock or security on a particular stock exchange. 
        You can find these symbols at [YahooFinance](https://finance.yahoo.com),
        for example. 

        (Examples) Symbol - Company:

        AAPL - Apple, Inc.

        MSFT - Microsoft Corporation

        TSLA - Tesla, Inc. 
        ''',
        placeholder='Example: AAPL, MSFT, TSLA'
    )

    submitted = st.form_submit_button(label='CONFIRM CHOICES', use_container_width=True)
    if 'submitted' not in st.session_state:
        st.session_state['submitted'] = submitted

if st.session_state['submitted']:

    # If user has not entered any ticker symbols
    if input_ticker_symbol == '':
        st.write('Please enter at least one ticker symbol.')

    # If user has entered a symbol
    else:

        tickers = {}                # Store yf.Ticker objects
        symbols = []                # Store symbols
        securities_invested = []    # Store security names

        # Remove whitespaces and separate by commas
        ticker_symbols = input_ticker_symbol.replace(' ', '').split(',')
        # Remove duplicates and sort alphabetically
        ticker_symbols = set(ticker_symbols)

        for ts in ticker_symbols:
            ticker = yf.Ticker(ts)

            # If symbol does not exist, ticker.info returns a dictionary of length 1
            if len(ticker.info) == 1:
                st.write(f'The ticker symbol {ts} was not found.')
            # If symbol does exist
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

                # Store security info
                if symbol not in tickers:
                    tickers[symbol] = ticker

                symbols.append(symbol)
                securities_invested.append(security_name)

        NUM_SECURITIES_INVESTED = len(securities_invested)
        if NUM_SECURITIES_INVESTED == 0:
            st.write(
                'Sorry, no data was found for the symbols you entered. Make sure they are correct.'
            )
        else:

            # Create pandas DataFrame with info about each buy order
            # Columns: Investment date, symbol, amount of shares bought, buy price
            rows = []   # Build DataFrame with list of lists (each list is a row)

            INVESTMENT_EXISTS = False   # Flag to output message if no investment exists

            # Use session_state to store yfinance data and
            # avoid downloading from yfinance after slider update
            if 'dfs_downloads' not in st.session_state:
                st.session_state['dfs_downloads'] = {}  # DataFrames of symbols with retrieved data

            # Get the buy price for each investment date and symbol
            current_investment_date = datetime.date(
                day=date_start.day,
                month=date_start.month,
                year=date_start.year
            )

            while current_investment_date <= date_end:
                for symbol in sorted(symbols):
                    # Create unique key for search parameters to store
                    # yfinance data in session_state
                    key = f'{symbol}//{date_start}//{date_end}//{investment_frequency}//{investment_amount}'
                    if key not in st.session_state['dfs_downloads']:
                        df_security = yf.download(
                            tickers=symbol,
                            start=date_start,
                            end=date_end,
                            actions=True
                        )

                        # If no data was found for symbol
                        if len(df_security) == 0:
                            st.write(
                                f'''
                                Unfortunately no price data was found for {symbol} from
                                {date_start:%B %d %Y} until {date_end:%B %d %Y}.
                                '''
                            )

                            continue

                        # Store yfinance data under unique key in session_state
                        st.session_state['dfs_downloads'][key] = df_security

                    # Shorter variable name to avoid typing session_state...
                    dfs_downloads = st.session_state['dfs_downloads'].copy()
                    # Create row for DataFrame
                    row = []

                    # If market is open, buy on investment date
                    market_open_dates = dfs_downloads[key].index.date
                    is_market_open = current_investment_date in market_open_dates
                    if is_market_open:
                        buy_price_original = dfs_downloads[key].loc[
                            market_open_dates == current_investment_date,
                            'Open'
                        ].iloc[0]

                        actual_investment_date = current_investment_date
                        INVESTMENT_EXISTS = True

                    # If market is closed, buy at next market open
                    else:
                        is_future_date = market_open_dates > current_investment_date
                        # If market has not opened yet in the future, break
                        if is_future_date.sum() == 0:
                            st.write(
                                f'''
                                No market data was found for {symbol} scheduled investment
                                on {current_investment_date} or the following market open.
                                '''
                            )
                            break

                        # If market has opened in the future, buy in first opportunity
                        future_dates = dfs_downloads[key].loc[is_future_date]
                        next_market_open = future_dates.reset_index().iloc[0]
                        buy_price_original = next_market_open['Open']
                        actual_investment_date = next_market_open['Date'].date()
                        INVESTMENT_EXISTS = True

                    # Convert buy price from security's currency to base currency
                    currency_security = tickers[symbol].info['currency']
                    if currency_security == base_currency:
                        buy_price_converted = buy_price_original
                    else:
                        buy_price_converted = helper.curr_conv.convert(
                            amount=buy_price_original,
                            currency=currency_security,
                            new_currency=base_currency,
                            date=actual_investment_date,
                        )

                    # Allow for fractional shares if buy price is bigger
                    num_shares_bought = investment_amount / buy_price_converted

                    # Add DataFrame row elements
                    row.append(actual_investment_date)
                    row.append(symbol)
                    row.append(tickers[symbol].info['quoteType'])
                    row.append(currency_security)
                    row.append(num_shares_bought)
                    row.append(buy_price_original)
                    row.append(buy_price_converted)
                    row.append(investment_amount)
                    rows.append(row)

                # Once the investment date is covered for
                # all symbols, move on to next date
                current_investment_date = helper.update_investment_date(
                    current_investment_date,
                    investment_frequency
                )

            # If unable to execute any buy orders
            if not INVESTMENT_EXISTS:
                st.write(
                    '''
                    There was no data retrieved for any investments between the selected
                    start and end dates. Perhaps try a different investment day.
                    '''
                )

            # If able to execute at least 1 buy order
            else:
                first_investment_date = rows[0][0]
                last_investment_date = rows[-1][0]

                st.write(
                    f'''
                    You will invest in the following {NUM_SECURITIES_INVESTED}
                    [{'security' if NUM_SECURITIES_INVESTED == 1 else 'securities'}](
                    https://www.investopedia.com/terms/s/security.asp) on a
                    {investment_frequency.lower()} basis from the first available
                    investment date ({first_investment_date:%B %d, %Y}) until the last
                    available investment date ({last_investment_date:%B %d, %Y}).
                    '''
                )

                # Write out the different securities to invest in
                NUM_COLS = 4
                cols_securities = st.columns(NUM_COLS)
                for i, security in enumerate(sorted(securities_invested)):
                    with cols_securities[i%NUM_COLS]:
                        st.write(f'{i+1}. {security}')

                # Create monthly investments DataFrame from rows
                df_investments = pd.DataFrame(
                    data=rows,
                    columns=[
                        'Purchase Date',
                        'Symbol',
                        'Security Type',
                        'Original Currency',
                        'Shares Bought', 
                        'Share Price at Purchase (Original Currency)',
                        f'Share Price at Purchase ({base_currency})',
                        f'Invested Capital ({base_currency})'
                    ]
                )

                # When investing daily and meeting a closed market date,
                # the simulation would invest twice in the next open date
                if investment_frequency == 'Daily':
                    df_investments.drop_duplicates(['Purchase Date', 'Symbol'], inplace=True)

                # Convert to datetime.date
                df_investments['Purchase Date'] = pd.to_datetime(df_investments['Purchase Date']).dt.date
                df_investments.sort_values(['Purchase Date', 'Symbol'], inplace=True)
                df_investments.reset_index(drop=True, inplace=True)

                st.header('Transactions', divider='rainbow')
                st.write('Your periodic investments are shown below.')
                df_investments.index += 1
                df_investments_show = df_investments.copy()
                for col in ['Share Price at Purchase (Original Currency)', f'Share Price at Purchase ({base_currency})']:
                    df_investments_show[col] = df_investments_show[col].round(2)
                st.dataframe(df_investments_show, use_container_width=True)

                #################### FIND INVESTMENT VALUE ####################
                # Generate key for correct yfinance data retrieval
                df_investments['Key'] = df_investments['Symbol'] + f'//{date_start}//{date_end}//{investment_frequency}//{investment_amount}'
                # Match values from dictionary to DataFrame row values and add data to that row
                df_investments['Current Share Price (Original Currency)'] = df_investments['Key'].apply(
                    lambda x: dfs_downloads[x]['Close'].iloc[-1]
                )

                # Convert share price
                df_investments[f'Current Share Price ({base_currency})'] = df_investments.apply(
                    lambda row: helper.curr_conv.convert(
                        amount=row['Current Share Price (Original Currency)'],
                        currency=row['Original Currency'],
                        new_currency=base_currency,
                        date=date_end
                    ),
                    axis=1
                )

                # Calculate for each day within date range
                df_investments[f'Current Investment Value ({base_currency})'] = df_investments['Shares Bought'] * df_investments[f'Current Share Price ({base_currency})']
                df_investments[f'Unrealised Gain/Loss ({base_currency})'] = df_investments[f'Current Investment Value ({base_currency})'] - investment_amount
                df_investments['Return on Investment (%)'] = (df_investments[f'Unrealised Gain/Loss ({base_currency})'] / investment_amount) * 100

                st.header('Development', divider='rainbow')

                st.write(
                    '''
                    - The metrics below show the overall [unrealised gain (or loss)](
                    https://www.investopedia.com/ask/answers/04/021204.asp) of the
                    scheduled investements over a time period, as well as the
                    difference in [return on investment (ROI)](
                    https://www.investopedia.com/terms/r/returnoninvestment.asp) since then.

                    - You can click on the legend to show/hide each symbol.
                    '''
                )

                # Put together historical data for each symbol
                df_development_list = []
                correct_key_suffix = f'//{date_start}//{date_end}//{investment_frequency}//{investment_amount}'
                for symbol in symbols:
                    correct_key = symbol + correct_key_suffix
                    data = dfs_downloads[correct_key].copy()
                    data['Symbol'] = symbol
                    data = data[['Symbol', 'Open', 'Close', 'Dividends']]
                    df_development_list.append(data)

                # Combine all DataFrames into a single DataFrame
                df_development = pd.concat(df_development_list)
                df_development = df_development.sort_values(['Date', 'Symbol']).reset_index()
                df_development['Date'] = df_development['Date'].dt.date

                # For each day, track the user's investments' development
                cols_to_date = [
                    'Shares to Date',
                    f'Invested Capital to Date ({base_currency})',
                    f'Investment Value to Date ({base_currency})',
                    f'Unrealised Gain/Loss to Date ({base_currency})',
                    'Return on Investment (%)'
                ]

                df_development[cols_to_date] = df_development.apply(
                    lambda row: helper.get_values_to_date(row, df_investments, base_currency),
                    axis=1,
                    result_type='expand'
                )

                # Keep only dates where all symbols have data
                counts = df_development['Date'].value_counts()
                dates_with_all_symbols = counts.index[counts.eq(NUM_SECURITIES_INVESTED)]
                dates_with_all_symbols = df_development['Date'].isin(dates_with_all_symbols)
                df_all_symbols_per_date = df_development.loc[dates_with_all_symbols].copy()
                # Aggregate symbols by date
                cols_agg = ['Invested Capital', 'Investment Value', 'Unrealised Gain/Loss']
                cols_agg = [f'{col} to Date ({base_currency})' for col in cols_agg]
                df_grouped = df_all_symbols_per_date.groupby('Date')[cols_agg].sum()
                df_grouped = df_grouped.reset_index()
                df_grouped['Return on Investment (%)'] = (df_grouped[f'Unrealised Gain/Loss to Date ({base_currency})'] / df_grouped[f'Invested Capital to Date ({base_currency})']) * 100
                df_grouped['Symbol'] = '--OVERALL--'

                # Display period performance metrics
                metrics = ['1D', '1W', '1M', '6M', 'YTD', '1Y', '5Y', 'MAX']
                metric_cols = st.columns(len(metrics))  # Show metrics horizontally
                for col_idx, metric in enumerate(metrics):
                    # Calculate metric
                    metric_gain_loss, metric_pct_change = helper.calculate_development_metric(
                        metric,
                        df_grouped.loc[df_grouped['Symbol'] == '--OVERALL--'],
                        base_currency
                    )

                    # Show metric
                    with metric_cols[col_idx]:
                        st.metric(
                            label=f'{metric} ({base_currency})',
                            value=metric_gain_loss,
                            delta=metric_pct_change,
                            delta_color='off' if metric_pct_change == '-' else 'normal'
                        )

                # Add overall performance to development data
                df_development_plot = pd.concat([df_development, df_grouped], ignore_index=True)
                df_development_plot = df_development_plot.sort_values(['Date', 'Symbol'])
                df_development_plot = df_development_plot.reset_index(drop=True)
                # df_development_plot.index += 1
                # st.dataframe(df_development_plot, use_container_width=True)

                # Plot gain/loss and return on investment in separate tabs
                tab_gain_loss, tab_pct_return = st.tabs(
                    ['Unrealised Gain/Loss', 'Return on Investment']
                )

                with tab_gain_loss:
                    fig_gain_loss = px.line(
                        df_development_plot,
                        x='Date',
                        y=f'Unrealised Gain/Loss to Date ({base_currency})',
                        color='Symbol'
                    )

                    # Show hover-data together: https://plotly.com/python/hover-text-and-formatting/
                    # Change y-axis format: https://plotly.com/python/tick-formatting/
                    fig_gain_loss.update_traces(hovertemplate=None)
                    fig_gain_loss.update_layout(
                        yaxis_title=f'Unrealised Gain/Loss ({base_currency})',
                        hovermode='x unified',
                        yaxis_tickformat=','
                    )

                    st.plotly_chart(fig_gain_loss)

                with tab_pct_return:

                    df_development_plot['Return on Investment'] = df_development_plot['Return on Investment (%)'] / 100

                    fig_pct_return = px.line(
                        df_development_plot,
                        x='Date',
                        y='Return on Investment',
                        color='Symbol',
                    )

                    fig_pct_return.update_traces(hovertemplate=None)
                    fig_pct_return.update_layout(
                        hovermode='x unified',
                        yaxis_tickformat='.0%',
                    )

                    # Show only overall performance line initially
                    # https://stackoverflow.com/questions/74322004/how-to-have-one-item-in-the-legend-selected-by-default-in-plotly-dash
                    fig_pct_return.update_traces(visible='legendonly')
                    for idx, data in enumerate(fig_pct_return.data):
                        if data['name'] == '--OVERALL--':
                            fig_pct_return.data[idx].visible = True
                            break

                    st.plotly_chart(fig_pct_return, use_container_width=True)
                    df_development_plot = df_development_plot.drop('Return on Investment', axis=1)

                st.header('Portfolio Distribution', divider='rainbow')

                # Slider to update pie chart over time
                date_slider = st.slider(
                    label='Analyse portofolio distribution by date',
                    min_value=df_all_symbols_per_date['Date'].min(),
                    max_value=df_all_symbols_per_date['Date'].max(),
                    format='MMM D, YYYY'
                )

                # Get values up until slider date
                df_pie = df_all_symbols_per_date.copy()
                df_pie = df_pie.loc[df_pie['Date'] <= date_slider]
                # Only the last values for each security are needed
                df_pie = df_pie.iloc[-NUM_SECURITIES_INVESTED:]

                # Plot invested capital and actual value in separate columns
                colums_pie_streamlit = st.columns(2)
                cols_pie = [
                    f'Invested Capital to Date ({base_currency})',
                    f'Investment Value to Date ({base_currency})',
                ]

                # Return on investment values
                invested_capital = df_pie[cols_pie[0]].sum()
                investment_value = df_pie[cols_pie[1]].sum()
                roi = (investment_value - invested_capital) / invested_capital
                roi *= 100

                # Get last values for each security, add them together
                # and plot the pie chart
                for idx, col_df in enumerate(cols_pie):
                    total_amount = df_pie[col_df].sum()
                    # Capital as int, value as float
                    total_amount = round(total_amount) if idx == 0 else round(total_amount, 2)

                    if col_df == f'Investment Value to Date ({base_currency})':
                        DELTA = f'{roi:.2f}%'
                    else:
                        DELTA = None

                    with colums_pie_streamlit[idx]:
                        st.metric(label=col_df, value=total_amount, delta=DELTA)
                        fig_pie = px.pie(
                            df_pie,
                            values=col_df,
                            names='Symbol'
                        )
                        st.plotly_chart(fig_pie)

                st.header('Dividends', divider='rainbow')

                # Get dividends
                is_dividend = df_development['Dividends'] != 0
                if is_dividend.sum() == 0:
                    st.write(
                        f'''
                        There are no dividends for any of your investments
                        during the period {date_start:%B %d %Y} until {date_end:%B %d %Y}.
                        '''
                    )
                else:

                    dividends = df_development.loc[is_dividend]

                    dividends = dividends.reset_index(drop=True)
                    dividends = dividends.rename(
                        columns={'Dividends': 'Dividend per Share (Original Currency)'}
                    )

                    # Convert dividends to base currency
                    dividends[['Original Currency', f'Dividend per Share ({base_currency})']] = dividends.apply(
                        lambda x: helper.convert_dividends(x, base_currency, df_investments),
                        axis=1,
                        result_type='expand'
                    )

                    # Calculate income from dividends
                    dividends[f'Dividend Income ({base_currency})'] = dividends[f'Dividend per Share ({base_currency})'] * dividends['Shares to Date']
                    dividends[f'Dividend Income ({base_currency})'] = dividends[f'Dividend Income ({base_currency})'].round(2)
                    dividends = dividends[
                        [
                            'Date',
                            'Symbol',
                            'Shares to Date',
                            'Dividend per Share (Original Currency)',
                            f'Dividend per Share ({base_currency})',
                            f'Dividend Income ({base_currency})'
                        ]
                    ]

                    # Show dividends over time
                    dividends.index += 1
                    st.dataframe(dividends, use_container_width=True)

                    # Plot dividend income by symbol
                    fig_dividends = px.bar(
                        data_frame=dividends,
                        x='Symbol',
                        y=f'Dividend Income ({base_currency})',
                        hover_data=['Date', 'Symbol', f'Dividend Income ({base_currency})']
                    )

                    st.plotly_chart(fig_dividends)

                st.header('DCA vs Lump Sum vs Inflation', divider='rainbow')
                cols_of_interest = ['Date', 'Invested Capital to Date (USD)', 'Unrealised Gain/Loss to Date (USD)', 'Return on Investment (%)']
                # Compare DCA performance vs lump sum vs inflation
                # Use https://pypi.org/project/cpi/ for inflation
                # Convert everything to dollars since cpi is USD based

                # Check https://github.com/TariqAHassan/EasyMoney and
                # https://medium.com/@lucamingarelli/easy-access-to-ecb-data-in-python-6015b65dcc0efor EUR based

                tab_dca_gain_loss, tab_dca_return = st.tabs(
                    ['Unrealised Gain/Loss', 'Return on Investment']
                )

                # DCA
                df_dca = df_development_plot.loc[df_development_plot['Symbol'] == '--OVERALL--'].copy()
                df_dca['Method'] = 'DCA'
                st.dataframe(
                    df_dca[cols_of_interest],
                    use_container_width=True
                )

                # Lump Sum
                lump_sum = df_dca[f'Invested Capital to Date ({base_currency})'].iloc[-1]
                lump_sum_per_security = lump_sum / NUM_SECURITIES_INVESTED
                df_lump_sum = df_development[['Date', 'Symbol', 'Open', 'Close']].copy()
                df_lump_sum['Method'] = 'Lump Sum'
                data_lump_sum = []  # Store DataFrames for development of each symbol to then concat
                for symbol in df_lump_sum['Symbol'].unique():
                    data = df_lump_sum.loc[df_lump_sum['Symbol'] == symbol].copy()
                    data['Shares to Date'] = lump_sum_per_security / data['Open'].iloc[0]
                    data[f'Invested Capital to Date ({base_currency})'] = lump_sum_per_security
                    data[f'Investment Value to Date ({base_currency})'] = data['Shares to Date'] * data['Close']
                    data[f'Unrealised Gain/Loss to Date ({base_currency})'] = data[f'Investment Value to Date ({base_currency})'] - lump_sum_per_security
                    data_lump_sum.append(data)

                df_lump_sum = pd.concat(data_lump_sum, ignore_index=True)
                df_lump_sum = df_lump_sum.sort_values(['Date', 'Symbol']).reset_index(drop=True)

                # Keep only dates where all symbols have data
                counts = df_lump_sum['Date'].value_counts()
                dates_with_all_symbols = counts.index[counts.eq(NUM_SECURITIES_INVESTED)]
                dates_with_all_symbols = df_lump_sum['Date'].isin(dates_with_all_symbols)
                df_all_symbols_per_date = df_lump_sum.loc[dates_with_all_symbols].copy()
                # Aggregate symbols by date
                cols_agg = ['Invested Capital', 'Investment Value', 'Unrealised Gain/Loss']
                cols_agg = [f'{col} to Date ({base_currency})' for col in cols_agg]
                df_lump_sum = df_all_symbols_per_date.groupby('Date')[cols_agg].sum()
                df_lump_sum = df_lump_sum.reset_index()
                df_lump_sum['Return on Investment (%)'] = (df_lump_sum[f'Unrealised Gain/Loss to Date ({base_currency})'] / df_lump_sum[f'Invested Capital to Date ({base_currency})']) * 100
                df_lump_sum['Symbol'] = '--OVERALL--'
                st.dataframe(df_lump_sum[cols_of_interest], use_container_width=True)

                # Inflation
                # Reuse lump sum columns
                df_inflation = df_lump_sum.copy()

                if base_currency != 'USD':
                    df_inflation['Invested Capital to Date (USD)'] = df_lump_sum.apply(
                        lambda row: helper.curr_conv.convert(
                            amount=row[f'Invested Capital to Date ({base_currency})'],
                            currency=base_currency,
                            new_currency='USD',
                            date=row['Date']
                        ),
                        axis=1
                    )

                inflation_key = f'inflation//{'//'.join(sorted(symbols))}{correct_key_suffix}'
                if inflation_key not in st.session_state:
                    buying_power_by_month = helper.get_monthly_inflation_adjusted_buying_power(df_inflation)
                    st.session_state[inflation_key] = buying_power_by_month

                # Adjusted buying power nicknamed as investment value
                df_inflation['Investment Value to Date (USD)'] = df_inflation.apply(
                    lambda row: st.session_state[inflation_key][
                        datetime.date(
                            day=1,
                            month=row['Date'].month,
                            year=row['Date'].year
                        )
                    ],
                    axis=1
                )

                df_inflation['Unrealised Gain/Loss to Date (USD)'] = df_inflation['Investment Value to Date (USD)'] - df_inflation['Invested Capital to Date (USD)']
                df_inflation['Return on Investment (%)'] = 100 * (df_inflation['Unrealised Gain/Loss to Date (USD)'] / df_inflation['Invested Capital to Date (USD)'])
                st.dataframe(df_inflation[cols_of_interest], use_container_width=True)

                with tab_dca_gain_loss:

                    fig_dca_vs_lump_sum_gain_loss = px.line()

                    fig_dca_vs_lump_sum_gain_loss.add_scatter(
                        name='DCA',
                        x=df_dca['Date'],
                        y=df_dca['Unrealised Gain/Loss to Date (USD)']
                    )

                    fig_dca_vs_lump_sum_gain_loss.add_scatter(
                        name='Lump Sum',
                        x=df_lump_sum['Date'],
                        y=df_lump_sum['Unrealised Gain/Loss to Date (USD)'].round(2)
                    )

                    fig_dca_vs_lump_sum_gain_loss.add_scatter(
                        name='Adjusted Buying Power (after Inflation)',
                        x=df_inflation['Date'],
                        y=df_inflation['Unrealised Gain/Loss to Date (USD)'].round(2)
                    )

                    fig_dca_vs_lump_sum_gain_loss.update_traces(hovertemplate=None)
                    fig_dca_vs_lump_sum_gain_loss.update_layout(
                        yaxis_title='Unrealised Gain/Loss (USD)',
                        hovermode='x unified',
                        yaxis_tickformat=','
                    )

                    st.plotly_chart(fig_dca_vs_lump_sum_gain_loss, use_container_width=True)

                with tab_dca_return:

                    fig_dca_vs_lump_sum_return = px.line()

                    fig_dca_vs_lump_sum_return.add_scatter(
                        name='DCA',
                        x=df_dca['Date'],
                        y=df_dca['Return on Investment (%)'] / 100
                    )

                    fig_dca_vs_lump_sum_return.add_scatter(
                        name='Lump Sum',
                        x=df_lump_sum['Date'],
                        y=df_lump_sum['Return on Investment (%)'] / 100
                    )

                    fig_dca_vs_lump_sum_return.add_scatter(
                        name='Adjusted Buying Power (after Inflation)',
                        x=df_inflation['Date'],
                        y=df_inflation['Return on Investment (%)'] / 100
                    )

                    fig_dca_vs_lump_sum_return.update_traces(hovertemplate=None)
                    fig_dca_vs_lump_sum_return.update_layout(
                        yaxis_title='Return on Investment',
                        hovermode='x unified',
                        yaxis_tickformat='.0%',
                    )

                    st.plotly_chart(fig_dca_vs_lump_sum_return)
