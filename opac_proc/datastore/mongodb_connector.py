# coding: utf-8
import os
import sys
import logging

from mongoengine import register_connection, connect

# Import path
PROJECT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
sys.path.append(PROJECT_PATH)

from opac_proc.web import config
from opac_proc.helpers.MongoLogger import MongoLogger

# Setup
logger = logging.getLogger(__name__)
mongo_logger = MongoLogger


class MongoDbConnector(object):
    def get_settings_connection(self, db_name, settings):
        settings_mongo = {
            'name': db_name,
            'host': settings['host'],
            'port': settings['port'],
        }

        if 'username' in settings and 'password' in settings:
            settings_mongo['username'] = settings['username']
            settings_mongo['password'] = settings['password']

        return settings_mongo

    def connect_at_proc(self):
        # Log
        MongoLogger.connect()

        # Get MongoDB settings
        config_settings = self.get_settings_connection(
            db_name=config.OPAC_PROC_MONGODB_NAME,
            settings=config.OPAC_PROC_MONGODB_SETTINGS
        )

        # Create connection
        return register_connection(config_settings['name'], **config_settings)


def register_connections():
    mongo_connector = MongoDbConnector()

    # OPAC PROC
    mongo_connector.connect_at_proc()

    # OPAC WEBAPP
    opac_webapp_db_name = get_opac_webapp_db_name()
    logger.debug(u'Registrando conexão - {db}: mongo://{host}:{port}/{db}'.format(
        **config.OPAC_WEB_APP_MONGODB_SETTINGS))

    opac_webapp_connection = {
        'name': opac_webapp_db_name,
        'host': config.OPAC_WEB_APP_MONGODB_SETTINGS['host'],
        'port': config.OPAC_WEB_APP_MONGODB_SETTINGS['port'],
    }

    if 'username' in config.OPAC_WEB_APP_MONGODB_SETTINGS and 'password' in config.OPAC_WEB_APP_MONGODB_SETTINGS:
        opac_webapp_connection['username'] = config.OPAC_WEB_APP_MONGODB_SETTINGS['username']
        opac_webapp_connection['password'] = config.OPAC_WEB_APP_MONGODB_SETTINGS['password']
    register_connection(opac_webapp_db_name, **opac_webapp_connection)

    # OPAC PROC LOGS
    opac_logs_db_name = get_opac_logs_db_name()
    logger.debug(u'Registrando conexão - {db}: mongo://{host}:{port}/{db}'.format(
        **config.OPAC_PROC_LOG_MONGODB_SETTINGS))

    opac_logs_connection = {
        'name': opac_logs_db_name,
        'host': config.OPAC_PROC_LOG_MONGODB_SETTINGS['host'],
        'port': config.OPAC_PROC_LOG_MONGODB_SETTINGS['port'],
    }

    if 'username' in config.OPAC_PROC_LOG_MONGODB_SETTINGS and 'password' in config.OPAC_PROC_LOG_MONGODB_SETTINGS:
        opac_logs_connection['username'] = config.OPAC_PROC_LOG_MONGODB_SETTINGS['username']
        opac_logs_connection['password'] = config.OPAC_PROC_LOG_MONGODB_SETTINGS['password']
    register_connection(opac_logs_db_name, **opac_logs_connection)


def get_opac_proc_db_name():
    return config.OPAC_PROC_MONGODB_NAME


def get_opac_webapp_db_name():
    return config.OPAC_WEB_APP_MONGODB_NAME


def get_opac_logs_db_name():
    return config.OPAC_PROC_LOG_MONGODB_NAME


# Conexão utilizada para site web
def get_db_connection():
    if config.OPAC_PROC_MONGODB_USER and config.OPAC_PROC_MONGODB_PASS:
        msg = u'Iniciando conexão - com credenciais do banco: mongo://{username}:{password}@{host}:{port}/{db}'.format(
            **config.OPAC_PROC_MONGODB_SETTINGS)
        logger.debug(msg)
    else:
        msg = u'Iniciando conexão - sem credenciais do banco: mongo://{host}:{port}/{db}'.format(
            **config.OPAC_PROC_MONGODB_SETTINGS)
        logger.debug(msg)
    try:
        db = connect(**config.OPAC_PROC_MONGODB_SETTINGS)
    except Exception as e:  # melhorar captura da Exceção
        msg = u"Não é possível conectar com banco de dados mongo. %s", str(e)
        logger.error(msg)
    else:
        db_name = get_opac_proc_db_name()
        msg = u"Conexão establecida com banco: %s!" % db_name
        logger.info(msg)
        return db
