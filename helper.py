"""Helper functions for investing simulator Streamlit app"""

import datetime
from dateutil.relativedelta import relativedelta
from currency_converter import CurrencyConverter

curr_conv = CurrencyConverter(
    fallback_on_missing_rate=True,
    fallback_on_wrong_date=True
)

def update_investment_date(investment_date, investment_frequency):
    """
    Increase investment date by user's investment frequency

    :param investment_date: Scheduled investment date
    :type investment_date: datetime.date
    :param investment_frequency: One of 'Daily', 'Weekly' or 'Monthly'
    :type investment_frequency: str
    :return: Next scheduled investment date
    :rtype: datetime.date
    """

    if investment_frequency == 'Daily':
        investment_date += relativedelta(days=1)
    elif investment_frequency == 'Weekly':
        investment_date += relativedelta(weeks=1)
    else:
        investment_date += relativedelta(months=1)

    return investment_date

def get_values_to_date(row, df_investments, base_currency):
    """
    Tracks the user's investments' development on a daily basis

    :param df_investments: DataFrame of the user's investments
    :type df_investments: pd.DataFrame
    :param row: Row of DataFrame
    :type row:
    :param base_currency: Currency of user's investments
    :type base_currency: str
    :return: Number of shares owned up to a date, invested capital to date,
             investment value to date, investment gain to date and
             profit in percentage
    :rtype:
    """

    # For each row of the development DataFrame, find the user's
    # previous investments on each symbol
    is_prior_date = df_investments['Purchase Date'] <= row['Date']
    is_same_symbol = df_investments['Symbol'] == row['Symbol']
    past_data = df_investments.loc[is_prior_date & is_same_symbol]

    # Sum up the shares and capital invested up until the row's date
    num_shares_to_date = past_data['Shares Bought'].sum()
    invested_capital_to_date = round(past_data[f'Invested Capital ({base_currency})'].sum(), 2)

    close_price_converted = curr_conv.convert(
        amount=row['Close'],
        currency=past_data['Original Currency'].iloc[0],
        new_currency=base_currency,
        date=row['Date']
    )

    investment_value_to_date = round(num_shares_to_date * close_price_converted, 2)
    unrealised_gain_or_loss = investment_value_to_date - invested_capital_to_date
    profit_to_date = round((unrealised_gain_or_loss / invested_capital_to_date) * 100, 2)
    return num_shares_to_date, invested_capital_to_date, investment_value_to_date, unrealised_gain_or_loss, profit_to_date

def calculate_development_metric(metric, df_development, base_currency):
    """
    Calculate number for 1D, 1W, 1M, 6M, YTD, 1Y, 5Y, MAX metrics

    :param metric: One of 1D, 1W, 1M, 6M, YTD, 1Y, 5Y, MAX
    :type metric: str
    :param df_development: DataFrame with overall daily security development
    :type df_development: pandas.DataFrame
    :param base_currency: Currency in which to invest
    :type base_currency: str
    :return: Unrealised gain or loss
    :rtype: int
    :return: Percentual change
    :rtype: int
    """

    # If the development to track is that of the whole investment period
    # or the investment started after Jan 1st, then we can just use the
    # last values of the DataFrame without doing further calculations
    min_date = df_development['Date'].min()
    max_date = df_development['Date'].max()
    january_1st = datetime.date(day=1, month=1, year=max_date.year)

    if metric == 'MAX' or (metric == 'YTD' and min_date > january_1st):
        gain = df_development[f'Unrealised Gain/Loss to Date ({base_currency})'].iloc[-1]
        pct_change = df_development['Percentage Return'].iloc[-1]

    else:

        # Calculate last date
        last_dates = {
            '1D': max_date - relativedelta(days=1),
            '1W': max_date - relativedelta(weeks=1),
            '1M': max_date - relativedelta(months=1),
            '6M': max_date - relativedelta(months=6),
            'YTD': january_1st,
            '1Y': max_date - relativedelta(years=1),
            '5Y': max_date - relativedelta(years=5)
        }

        last_date = last_dates[metric]
        df_before_date = df_development.loc[df_development['Date'] <= last_date]
        if len(df_before_date) == 0:    # If no investments that long ago
            return '-', '-'

        gain_before = df_before_date[f'Unrealised Gain/Loss to Date ({base_currency})'].iloc[-1]
        gain_now = df_development[f'Unrealised Gain/Loss to Date ({base_currency})'].iloc[-1]
        gain = gain_now - gain_before

        pct_before = df_before_date['Percentage Return'].iloc[-1]
        pct_now = df_development['Percentage Return'].iloc[-1]
        pct_change = pct_now - pct_before

    gain = f'{'+' if gain >= 0 else ''}{gain:.2f}'
    pct_change = f'{pct_change:.2f}%'

    return gain, pct_change

def convert_dividends(row, base_currency, df_investments):
    """
    Convert dividends to user's currency.

    :return: Converted dividends
    :rtype: float
    """

    is_same_symbol = row['Symbol'] == df_investments['Symbol']
    original_currency = df_investments.loc[is_same_symbol, 'Original Currency'].iloc[0]
    dividend_converted = round(
        curr_conv.convert(
            amount=row['Dividend per Share (Original Currency)'],
            currency=original_currency,
            new_currency=base_currency,
            date=row['Date']
        ),
        2
    )

    return original_currency, dividend_converted
