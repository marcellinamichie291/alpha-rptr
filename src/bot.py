# coding: UTF-8

import sys
import time
from datetime import datetime, timezone
from time import sleep

import json #pickle #jsonpickle #json
from hyperopt import fmin, tpe, STATUS_OK, STATUS_FAIL, Trials

from src import logger, notify
from src.exchange.bitmex.bitmex import BitMex
from src.exchange.binance_futures.binance_futures import BinanceFutures
from src.exchange.ftx.ftx import Ftx
from src.exchange.bitmex.bitmex_stub import BitMexStub
from src.exchange.binance_futures.binance_futures_stub import BinanceFuturesStub
from src.exchange.bitmex.bitmex_backtest import BitMexBackTest
from src.exchange.ftx.ftx_stub import FtxStub
from src.exchange.binance_futures.binance_futures_backtest import BinanceFuturesBackTest
from src.exchange.ftx.ftx_backtest import FtxBackTest


class Session:
    def __init__(self):
        self.__session_type__ = "object"
    def load(self, dict):
        self.__dict__.update(dict)


class Bot:
    # Parameters
    params = {}
    # Account
    account = None
    # Exchange
    exchange_arg = None
    # Time Frame
    bin_size = '1h'
    # Pair
    pair = 'BTCUSDT'
    # Periods
    periods = 20
    # Run on test net?
    test_net = False
    # Back test?
    back_test = False
    # Stub Test(paper trading)?
    stub_test = False
    # Parameter optimization?
    hyperopt = False
    # Session Persistence
    session = Session()
    # session = type("Session", (object,), {})()
    session_file = None
    session_file_name = None

    def __init__(self, bin_size):
        """
        constructor
        :param bin_size: time_frame
        :param periods: period
        """
        self.bin_size = bin_size

    def __del__(self):
        self.stop()

    def get_session(self):
        return self.session

    def set_session(self, session):
        self.session.load(session)

    def options(self):
        """
        Function to get values for parameter optimization
        """
        pass

    def ohlcv_len(self):
        """
        The length of the OHLC to the strategy
        """
        return 100

    def input(self, title, type, defval):
        """
        function to get param
        :param title: title of the parm
        :param defval: default value
        :return value
        """
        p = {} if self.params is None else self.params
        if title in p:
            return type(p[title])
        else:
            return defval

    def strategy(self, open, close, high, low, volume):
        """
        Strategy function, when creating a bot please inherit and implement this fn. 
        :param open: open price
        :param close: close price
        :param high: high price
        :param low: low price
        :param volume: volume
        """
        pass

    def params_search(self):
        """
 ˜      function to search params
        """
        def objective(args):
            logger.info(f"Params : {args}")
            try:
                if self.exchange_arg == "bitmex":
                    self.params = args
                    self.exchange = BitMexBackTest(account=self.account, pair=self.pair)
                    self.exchange.on_update(self.bin_size, self.strategy)
                    profit_factor = self.exchange.win_profit/self.exchange.lose_loss
                    logger.info(f"Profit Factor : {profit_factor}")
                    ret = {
                        'status': STATUS_OK,
                        'loss': 1/profit_factor
                    }
                if self.exchange_arg == 'binance':
                    self.params = args
                    self.exchange = BinanceFuturesBackTest(account=self.account, pair=self.pair)
                    self.exchange.on_update(self.bin_size, self.strategy)
                    profit_factor = self.exchange.win_profit/self.exchange.lose_loss
                    logger.info(f"Profit Factor : {profit_factor}")
                    ret = {
                        'status': STATUS_OK,
                        'loss': 1/profit_factor
                    }
                if self.exchange_arg == 'ftx':
                    self.params = args
                    self.exchange = FtxBackTest(account=self.account, pair=self.pair)
                    self.exchange.on_update(self.bin_size, self.strategy)
                    profit_factor = self.exchange.win_profit/self.exchange.lose_loss
                    logger.info(f"Profit Factor : {profit_factor}")
                    ret = {
                        'status': STATUS_OK,
                        'loss': 1/profit_factor
                    }
            except Exception as e:
                ret = {
                    'status': STATUS_FAIL
                }

            return ret

        trials = Trials()
        best_params = fmin(objective, self.options(), algo=tpe.suggest, trials=trials, max_evals=200)
        logger.info(f"Best params is {best_params}")
        logger.info(f"Best profit factor is {1/trials.best_trial['result']['loss']}")

    def run(self):
        """
˜       Function to run the bot
        """
        if self.hyperopt:
            logger.info(f"Bot Mode : Hyperopt")
            self.params_search()
            return

        elif self.stub_test:
            logger.info(f"Bot Mode : Stub")
            if self.exchange_arg == "binance":
                self.exchange = BinanceFuturesStub(account=self.account, pair=self.pair)
            elif self.exchange_arg == "bitmex":
                self.exchange = BitMexStub(account=self.account, pair=self.pair)
            elif self.exchange_arg == "ftx":
                self.exchange = FtxStub(account=self.account, pair=self.pair)
            else:
                logger.info(f"--exchange argument missing or invalid")
                return  
        elif self.back_test:
            logger.info(f"Bot Mode : Back test")
            if self.exchange_arg == "binance":
                self.exchange = BinanceFuturesBackTest(account=self.account, pair=self.pair)
            elif self.exchange_arg == "bitmex":
                self.exchange = BitMexBackTest(account=self.account, pair=self.pair)
            elif self.exchange_arg == "ftx":
                self.exchange = FtxBackTest(account=self.account, pair=self.pair)
            else:
                logger.info(f"--exchange argument missing or invalid")
                return
        else:
            logger.info(f"Bot Mode : Trade")
            if self.exchange_arg == "binance":
                self.exchange = BinanceFutures(account=self.account, pair=self.pair, demo=self.test_net)
            elif self.exchange_arg == "bitmex":
                self.exchange = BitMex(account=self.account, pair=self.pair, demo=self.test_net)
            elif self.exchange_arg == "ftx":
                self.exchange = Ftx(account=self.account, pair=self.pair, demo=self.test_net)
            else:
                logger.info(f"--exchange argument missing or invalid")
                return
        self.exchange.ohlcv_len = self.ohlcv_len()
        self.exchange.on_update(self.bin_size, self.strategy)

        logger.info(f"Starting Bot")
        logger.info(f"Strategy : {type(self).__name__}")
        logger.info(f"Balance : {self.exchange.get_balance()}")

        notify(f"Starting Bot\n"
               f"Strategy : {type(self).__name__}\n"
               f"Balance : {self.exchange.get_balance()}")
        
        self.exchange.show_result()

    def stop(self):
        """
˜       Function that stops the bot and cancel all trades.
        """
        if self.exchange is None:
            return

        logger.info(f"Stopping Bot")

        if self.session_file != None:
            self.session_file.truncate(0)
            self.session_file.seek(0)
            # pickle.dump(self.session, self.session_file)
            json.dump(self.session, self.session_file, default=vars, indent=True)
            # self.session_file.write(jsonpickle.encode(self.session))
            self.session_file.close()
            logger.info(f"Saved Session to {self.session_file_name}")

        self.exchange.stop()
        self.exchange.cancel_all()
        sys.exit(0)
