import os
from configparser import ConfigParser

from dotenv import dotenv_values

# Create a ConfigParser object
config = ConfigParser()

env = {
    **dotenv_values(".env.dev"),  # load shared development variables
    **dotenv_values(".env.secret"),  # load sensitive variables
    **os.environ,  # override loaded values with environment variables
}

_ = config.read("config.ini")
config = {**config, **env}  # merge config with environment variables
