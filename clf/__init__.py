import os.path
import logging
from flask import Flask


# Globals
app = Flask(__name__)
app.secret_key = '$*^%&#53r3ret56$%@#Res'
app.logger.setLevel(logging.DEBUG)
app.logger.addHandler(logging.StreamHandler())

cache_dir = os.path.join(os.path.dirname(__file__), 'cache')


# Plugins
from flask.ext.script import Manager
manager = Manager(app)


# Import views into context
import views

# Import commands into context
import commands

