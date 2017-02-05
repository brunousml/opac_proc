# coding: utf-8

import logging
from opac_proc.web import config

# Setup
logger = logging.getLogger(__name__)


class MongoLogger(object):
    @staticmethod
    def connect():
        # Message default
        msg = u'Iniciando conexão - sem credenciais do banco: mongo://{host}:{port}/{db}'.format(
            **config.OPAC_PROC_MONGODB_SETTINGS)

        if config.OPAC_PROC_MONGODB_USER and config.OPAC_PROC_MONGODB_PASS:
            msg = u'Iniciando conexão - com credenciais do banco: mongo://{username}:{password}@{host}:{port}/{db}'.format(
                **config.OPAC_PROC_MONGODB_SETTINGS)

        logger.debug(msg)

    @staticmethod
    def unsuccessful_connection(raw_except):
        logger.error(u"Não é possível conectar com banco de dados mongo. \n Raw Exception: \n %s", str(raw_except))

    @staticmethod
    def successful_connection():
        logger.info(u"Conexão establecida com banco: %s!" % config.OPAC_PROC_MONGODB_NAME)

    @staticmethod
    def register_connection():
        logger.debug(u'Registrando conexão - {db}: mongo://{host}:{port}/{db}'.format(
            **config.OPAC_PROC_MONGODB_SETTINGS))
