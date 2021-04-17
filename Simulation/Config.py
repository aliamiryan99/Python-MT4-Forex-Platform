
class Config:
    DEBUG = False
    time_frame = "M1"
    time_frame_show = "D"
    balance = 80000
    leverage = 100
    spreads = {'EURUSD': 20, 'GBPUSD': 30, 'NZDUSD': 40, 'USDCAD': 40, 'USDCHF': 30, 'USDJPY': 30,
                     'AUDUSD': 30, 'XAUUSD': 50, 'XAGUSD': 50, 'US30USD': 60, 'USATECHUSD': 100, 'US500USD': 100}     # in point
    volume_digit = 2    # for example 2 -> at least 0.01 lot
    start_date = "01.02.2017 00:00:00.000"
    end_date = "01.01.2021 00:00:00.000"
    date_format = "%d.%m.%Y %H:%M:%S.%f"
    symbols_dict = {'EURUSD': 0, 'GBPUSD': 1, 'NZDUSD': 2, 'USDCAD': 3, 'USDCHF': 4, 'USDJPY': 5, 'AUDUSD': 6,
                    'XAUUSD': 7, 'XAGUSD': 8, 'US30USD': 9, 'USATECHUSD': 10, 'US500USD': 11}
    symbols_list = ['EURUSD', 'GBPUSD', 'NZDUSD', 'USDCAD', 'USDCHF', 'USDJPY', 'AUDUSD',
                    'XAUUSD', 'XAGUSD', 'US30USD', 'USATECHUSD', 'US500USD']
    categories_list = {'EURUSD': 'Major', 'GBPUSD': 'Major', 'NZDUSD': 'Major', 'USDCAD': 'Major', 'USDCHF': 'Major',
                       'USDJPY': 'Major', 'AUDUSD': 'Major', 'XAUUSD': 'Metal', 'XAGUSD': 'Metal', 'US30USD': 'CFD',
                       'USATECHUSD': 'CFD', 'US500USD': 'CFD'}
    symbols_pip = {'EURUSD': 5, 'GBPUSD': 5, 'NZDUSD': 5, 'USDCAD': 5, 'USDCHF': 5, 'USDJPY': 3,
                     'AUDUSD': 5, 'XAUUSD': 2, 'XAGUSD': 3, 'US30USD': 1, 'USATECHUSD': 2, 'US500USD': 2}
    symbols_pip_value = {'EURUSD': 10**5, 'GBPUSD': 10**5, 'NZDUSD': 10**5, 'USDCAD': 10**5, 'USDCHF': 10**5, 'USDJPY': 10**5,
                     'AUDUSD': 10**5, 'XAUUSD': 10**2, 'XAGUSD': 500, 'US30USD': 5, 'USATECHUSD': 20, 'US500USD': 20}
    symbols_show = {'EURUSD': 0, 'GBPUSD': 0, 'NZDUSD': 0, 'USDCAD': 0, 'USDCHF': 0, 'USDJPY': 0,
                    'AUDUSD': 0, 'XAUUSD': 0, 'XAGUSD': 0, 'US30USD': 0, 'USATECHUSD': 0, 'US500USD': 0}

