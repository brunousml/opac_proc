#!/usr/bin/python
# coding: utf-8

import os
import sys
import time
import signal
import textwrap
import optparse
import datetime
import logging.config
from uuid import uuid4
from lxml import etree
from StringIO import StringIO

import multiprocessing
from multiprocessing import Pool

from mongoengine import connect

import packtools
from opac_schema.v1 import models
from mongoengine import DoesNotExist
from thrift_clients import clients
from scieloh5m5 import h5m5
from opac_ssm_api import client

import config
import utils

articlemeta = clients.ArticleMeta(
    config.ARTICLE_META_THRIFT_DOMAIN,
    config.ARTICLE_META_THRIFT_PORT)

logger = logging.getLogger(__name__)


def init_worker():
    signal.signal(signal.SIGINT, signal.SIG_IGN)


def config_logging(logging_level='INFO', logging_file=None):

    allowed_levels = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL
    }

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    logger.setLevel(allowed_levels.get(logging_level, config.OPAC_PROC_LOG_LEVEL))

    if logging_file:
        hl = logging.FileHandler(logging_file, mode='a')
    else:
        hl = logging.StreamHandler()

    hl.setFormatter(formatter)
    hl.setLevel(allowed_levels.get(logging_level, 'INFO'))

    logger.addHandler(hl)

    return logger


def process_collection(collection):

    m_collection = models.Collection()
    m_collection._id = str(uuid4().hex)
    m_collection.acronym = collection.acronym
    m_collection.name = collection.name

    endpoint = 'ajx/publication/size'

    params = {
        'code': collection.acronym,
        'collection': collection.acronym,
        'field': 'citations'
    }

    references = utils.do_request_json('{0}/{1}'.format(config.OPAC_METRICS_URL, endpoint), params)

    params['field'] = 'documents'
    articles = utils.do_request_json('{0}/{1}'.format(config.OPAC_METRICS_URL, endpoint), params)

    params['field'] = 'issue'
    issues = utils.do_request_json('{0}/{1}'.format(config.OPAC_METRICS_URL, endpoint), params)

    params['field'] = 'issn'
    journals = utils.do_request_json('{0}/{1}'.format(config.OPAC_METRICS_URL, endpoint), params)

    metrics = models.CollectionMetrics()

    metrics.total_citation = int(references.get('total', 0))
    metrics.total_article = int(articles.get('total', 0))
    metrics.total_issue = int(issues.get('total', 0))
    metrics.total_journal = int(journals.get('total', 0))

    m_collection.metrics = metrics

    return m_collection.save()


def process_journal(issn_collection):

    issn, collection = issn_collection

    connect(**config.MONGODB_SETTINGS)

    try:
        journal = articlemeta.get_journal(collection=collection, code=issn)

        logger.info(u"Adicionando journal %s", journal.title)

        m_journal = models.Journal()

        # We have to define which id will be use to legacy journals.
        _id = str(uuid4().hex)
        m_journal._id = _id
        m_journal.jid = _id

        m_journal.created = datetime.datetime.now()
        m_journal.updated = datetime.datetime.now()

        # Set collection
        collection = models.Collection.objects.get(
            acronym__iexact=journal.collection_acronym)
        m_journal.collection = collection

        m_journal.subject_categories = journal.subject_areas
        m_journal.study_areas = journal.wos_subject_areas
        m_journal.current_status = journal.current_status
        m_journal.publisher_city = journal.publisher_loc

        # Alterar no opac_schema, pois o xylose retorna uma lista e o opac_schema
        # aguarda um string.
        m_journal.publisher_name = journal.publisher_name[0]
        m_journal.eletronic_issn = journal.electronic_issn
        m_journal.scielo_issn = journal.scielo_issn # v400 isis
        m_journal.print_issn = journal.print_issn
        m_journal.acronym = journal.acronym
        m_journal.previous_title = journal.previous_title

        m_journal.title = journal.title
        m_journal.title_iso = journal.abbreviated_iso_title

        missions = []
        for lang, des in journal.mission.items():
            m = models.Mission()
            m.language = lang
            m.description = des
            missions.append(m)

        m_journal.mission = missions

        timelines = []
        for status in journal.status_history:
            timeline = models.Timeline()
            timeline.reason = status[2]
            timeline.status = status[1]

            # Corrigir datetime
            timeline.since = utils.trydate(status[0])
            timelines.append(timeline)

        m_journal.timeline = timelines
        m_journal.short_title = journal.abbreviated_title
        m_journal.index_at = journal.wos_citation_indexes
        m_journal.updated = utils.trydate(journal.update_date)
        m_journal.created = utils.trydate(journal.creation_date)
        m_journal.copyrighter = journal.copyrighter
        if journal.publisher_country:
            m_journal.publisher_country = journal.publisher_country[1]
        m_journal.online_submission_url = journal.submission_url
        m_journal.publisher_state = journal.publisher_state
        m_journal.sponsors = journal.sponsors

        if journal.other_titles:
            other_titles = []
            for title in journal.other_titles:
                t = models.OtherTitle()
                t.title = title
                t.category = "other"
                other_titles.append(t)

            m_journal.other_titles = other_titles

        # Obtendo o ano atual
        year = datetime.datetime.now().year

        metrics = models.JounalMetrics()

        _h5m5 = h5m5.get(m_journal.scielo_issn, str(year))

        if _h5m5:
            metrics.total_h5_index = _h5m5['h5']
            metrics.total_h5_median = _h5m5['m5']

        m_journal.metrics = metrics

        m_journal.save()
    except Exception as e:
        logger.error(u"Exception %s. Processando Journal (ISSN: %s, Collection: %s)",
            str(e), issn, collection)


def process_issue(issn_collection):

    issn, collection = issn_collection

    connect(**config.MONGODB_SETTINGS)

    for issue in articlemeta.issues(collection=collection, issn=issn):

        m_issue = models.Issue()

        logger.info(u"Adicionando issue: %s - %s", issn, issue.label)

        # We have to define which id will be use to legacy journals.
        _id = str(uuid4().hex)
        m_issue._id = _id
        m_issue.iid = _id

        m_issue.created = datetime.datetime.now()
        m_issue.updated = datetime.datetime.now()

        m_issue.unpublish_reason = issue.publisher_id

        # Get Journal of the issue
        try:
            journal = models.Journal.objects.get(scielo_issn=issue.journal.scielo_issn)
            m_issue.journal = journal
        except Exception as e:
            logger.warning(u"Erro obtendo journal com ISSN: %s, Exception: %s", issue.journal.scielo_issn, str(e))

        m_issue.volume = issue.volume
        m_issue.number = issue.number

        m_issue.type = issue.type

        m_issue.start_month = issue.start_month
        m_issue.end_month = issue.end_month
        m_issue.year = int(issue.publication_date[:4])

        m_issue.label = issue.label
        m_issue.order = issue.order

        m_issue.pid = issue.publisher_id

        suppl_text = (issue.supplement_number or issue.supplement_volume) or ''

        m_issue.suppl_text = suppl_text if suppl_text != '0' else ''

        m_issue.save()

    process_last_issue(issn)
    process_volume_issue(issn)


def process_article(issn_collection):

    issn, collection = issn_collection

    connect(**config.MONGODB_SETTINGS)

    for article in articlemeta.articles(collection=collection, issn=issn):

        logger.info(u"Adicionando artigo: %s", article.publisher_id)

        m_article = models.Article()

        _id = str(uuid4().hex)
        m_article._id = _id
        m_article.aid = _id

        try:
            issue = models.Issue.objects.get(pid=article.issue.publisher_id)
            m_article.issue = issue
        except DoesNotExist as e:
            logger.warning(u"Artigo SEM issue. publisher_id: %s", str(article.publisher_id))
            continue
        except Exception as e:
            logger.error(u"Erro ao tentar acessar o atributo issue do artigo: %s, Erro %s", str(article.publisher_id), e)

        try:
            journal = models.Journal.objects.get(
                scielo_issn=article.journal.scielo_issn)
            m_article.journal = journal
        except Exception as e:
            logger.error(u"Erro: %s", e)

        m_article.title = article.original_title()

        if article.translated_abstracts():
            m_article.abstract_languages = article.translated_abstracts().keys()

        if article.translated_section():
            translated_sections = []

            for lang, title in article.translated_section().items():
                translated_section = models.TranslatedSection()
                translated_section.language = lang
                translated_section.name = title
                translated_sections.append(translated_section)

            m_article.sections = translated_sections

        m_article.section = article.original_section()

        if article.translated_titles():
            translated_titles = []

            for lang, title in article.translated_titles().items():
                translated_title = models.TranslatedTitle()
                translated_title.language = lang
                translated_title.name = title
                translated_titles.append(translated_title)

            m_article.translated_titles = translated_titles

        try:
            m_article.order = int(article.order)
        except ValueError as e:
            logger.error(u'Ordenação inválida: %s-%s', e, article.publisher_id)

        try:
            m_article.doi = article.doi
            m_article.is_aop = article.is_ahead_of_print

            m_article.created = datetime.datetime.now()
            m_article.updated = datetime.datetime.now()

            m_article.original_language = article.original_language()

            m_article.languages = list(set(article.languages() + m_article.abstract_languages))

            m_article.abstract = article.original_abstract()

            if article.authors:
                m_article.authors = ['%s, %s' % (author['surname'], author['given_names']) for author in article.authors]

        except Exception as e:
            logger.error(u"Erro inesperado: %s, %s", article.publisher_id, e)
            continue

        m_article.pid = article.publisher_id
        m_article.fpage = article.start_page
        m_article.lpage = article.end_page
        m_article.elocation = article.elocation

        if article.data_model_version == 'xml':
            m_article.xml = article.file_code(fullpath=True)

        pdfs = []

        if article.fulltexts():
            for text, val in article.fulltexts().items():
                if text == 'pdf':
                    dict_pdf = {}
                    for lang, url in val.items():
                        dict_pdf['lang'] = lang
                        dict_pdf['url'] = url

                    pdfs.append(dict_pdf)

        m_article.pdfs = pdfs

        m_article.save()

    process_ahead(issn)
    process_articles_ssm(issn)


def process_volume_issue(issn):

    logger.info("Alterando o tipo para os itens que são fascículo de volume...")

    connect(**config.MONGODB_SETTINGS)

    # Get last issue for each Journal
    journal = models.Journal.objects.get(scielo_issn=issn)

    logger.info(u"Coletando fascículo de volume do periódico: %s", journal.title)

    volume_issue = models.Issue.objects.filter(number=None).filter(type__ne='supplement').filter(type__ne='pressrelease')

    for issue in volume_issue:
        issue.type = "volume_issue"
        issue.save()


def process_ahead(issn):

    logger.info("Coletando ahead of print...")

    connect(**config.MONGODB_SETTINGS)

    # Get last issue for each Journal
    journal = models.Journal.objects.get(scielo_issn=issn)

    logger.info(u"Coletando ahead of print do periódico: %s", journal.title)

    issue = models.Issue.objects.filter(type='ahead').filter(journal=journal).order_by('-year', '-order').first()

    if issue:
        logger.info(u"Fascículos do tipo ahead mais recente, ano: %s", issue.year)

        outdated_aheads = models.Issue.objects.filter(type='ahead').filter(journal=journal).filter(_id__ne=issue.iid)

        logger.info(u"Alterando o tipo dos aheads antigos e mantendo o mais com o tipo 'ahead'")
        for outdated_ahead in outdated_aheads:
            logger.info(u"Alterando o tipo do ahead ano: %s para 'outdated_ahead'", outdated_ahead.year)
            outdated_ahead.type = 'outdated_ahead'
            outdated_ahead.save()

        logger.info(u"Varendo se existe artigos em ahead")
        article_in_ahead = []
        for article in models.Article.objects.filter(issue=issue.iid):
            article_in_ahead.append(article.id)

        if not article_in_ahead:
            logger.info(u"O periódico %s, não possui artigo em ahead", journal.title)
            issue.type = 'outdated_ahead'
            issue.save()
    else:
        logger.info(u"O periódico %s, não possui artigo em ahead", journal.title)


def process_last_issue(issn):

    logger.info("Cadastrando os últimos fascículos...")

    connect(**config.MONGODB_SETTINGS)

    # Get last issue for each Journal
    journal = models.Journal.objects.get(scielo_issn=issn)

    logger.info(u"Recuperando último fascículo journal: %s", journal.title)

    issue = models.Issue.objects.filter(journal=journal).filter(type__ne='ahead').order_by('-year', '-order').first()
    issue_count = models.Issue.objects.filter(journal=journal).count()

    if issue:
        last_issue = articlemeta.get_issue(code=issue.pid)

        m_last_issue = models.LastIssue()
        m_last_issue.volume = last_issue.volume
        m_last_issue.number = last_issue.number
        m_last_issue.year = last_issue.publication_date[:4]
        m_last_issue.start_month = last_issue.start_month
        m_last_issue.end_month = last_issue.end_month
        m_last_issue.iid = issue.iid

        if last_issue.sections:

            sections = []

            for _, items in last_issue.sections.iteritems():

                if items:

                    for k, v in items.iteritems():

                        section = models.TranslatedSection()
                        section.name = v.encode('utf-8')
                        section.language = k.encode('utf-8')

                        sections.append(section)

            m_last_issue.sections = sections

        journal.last_issue = m_last_issue
        journal.last_issue.label = last_issue.label
        journal.issue_count = issue_count
        journal.save()
    else:
        logger.info(u"Impossível recuperar o último fascículo para o períodico: %s", journal.title)


def process_articles_ssm(issn):

    connect(**config.MONGODB_SETTINGS)

    journal = models.Journal.objects.get(scielo_issn=issn)

    logger.info(u"Enviando os artigos do periódico: %s para SSM", journal.title)

    for article in models.Article.objects.filter(journal=journal):

        article.htmls = []
        article.save()

        if article.xml:
            # O caminho deve ser até o acrônimo do periódico.
            filename = os.path.join(config.ARTICLE_FILE_PATH, article.xml)

            try:
                fp = open(filename)
            except IOError:
                logger.error(u"Erro ao tentar coletar o arquivo %s", filename)
                continue

            try:

                list_dict_html = []
                xml_etree = etree.parse(StringIO(fp.read()))

                client_ssm = client.Client()


                for lang, output in packtools.HTMLGenerator.parse(xml_etree, valid_only=False):
                    dict_htmls = {}
                    source = etree.tostring(output, encoding="utf-8",
                                                    method="html",
                                                    doctype=u"<!DOCTYPE html>")

                    dict_htmls['lang'] = lang

                    metadata = {'lang': lang,
                                'issue': article.issue.legend,
                                'title': article.title,
                                'journal': article.journal.title,
                                'pid': article.pid}

                    file_path, _ = os.path.splitext(getattr(fp, 'name', None))

                    filename = os.path.basename(file_path)

                    ssm_push_id = client_ssm.add_asset(pfile=StringIO(source),
                                                       filename=utils.generate_filename(filename, 'html', lang),
                                                       filetype='html',
                                                       metadata=metadata)

                    time.sleep(3)

                    asset_info = client_ssm.get_asset_info(ssm_push_id)

                    dict_htmls['source'] = asset_info['url']

                    list_dict_html.append(dict_htmls)

                article.htmls = list_dict_html

                metadata = {'issue': article.issue.legend,
                            'title': article.title,
                            'journal': article.journal.title,
                            'pid': article.pid}

                ssm_push_id = client_ssm.add_asset(pfile=StringIO(source),
                                                   filename=utils.generate_filename(filename, 'xml'),
                                                   filetype='xml',
                                                   metadata=metadata)

                time.sleep(3)

                asset_info = client_ssm.get_asset_info(ssm_push_id)

                article.xml = asset_info['url']

                article.save()

            except Exception as e:
                logger.error(u"Erro ao tentar transformar artigo: %s, erro: %s", article.pid, e)
                pass


def bulk(options, pool):

    connect(**config.MONGODB_SETTINGS)
    logger.info(u"Removendo todos os registro de Periódicos")
    models.Journal.drop_collection()
    logger.info(u"Removendo todos os registro de Fascículo")
    models.Issue.drop_collection()
    logger.info(u"Removendo todos os registro de Artigo")
    models.Article.drop_collection()

    # Collection
    for col in articlemeta.collections():
        if col.acronym == options.collection:
            # Cadastra a coleção somente quando não existe na base de dados.
            if not models.Collection.objects.filter(acronym=options.collection):
                logger.info(u"Adicionado a coleção: %s" % options.collection)
                process_collection(col)

    # Get the number of ISSNs
    issns = [(journal.scielo_issn, options.collection) for journal in articlemeta.journals(collection=options.collection)]

    issns_list = utils.split_list(issns, options.process)

    for _, pissns in enumerate(issns_list):
        logger.info(u"Enviando para processamento os issns: %s", pissns)
        pool.map(process_journal, pissns)
        pool.map(process_issue, pissns)
        pool.map(process_article, pissns)
        poll.map(process_article(pissns))


def serial(options):

    connect(**config.MONGODB_SETTINGS)
    logger.info(u"Removendo todos os registro de Periódicos")
    models.Journal.drop_collection()
    logger.info(u"Removendo todos os registro de Fascículo")
    models.Issue.drop_collection()
    logger.info(u"Removendo todos os registro de Artigo")
    models.Article.drop_collection()

    # Collection
    for col in articlemeta.collections():
        if col.acronym == options.collection:
            # Cadastra a coleção somente quando não existe na base de dados.
            if not models.Collection.objects.filter(acronym=options.collection):
                logger.info(u"Adicionado a coleção: %s" % options.collection)
                process_collection(col)

    # Se não tem issns indicados no argparse, processa todos os itens
    if not options.issns:
        issns = [(journal.scielo_issn, options.collection) for journal in articlemeta.journals(collection=options.collection)]
    else:
        issns = [(issn, options.collection) for issn in options.issns]

    for pissns in issns:
        logger.info(u"Enviando para processamento os issns: %s, %s" % pissns)
        process_journal(pissns)
        process_issue(pissns)
        process_article(pissns)


def run(options, pool):

    logger.info(u'Coleção alvo: %s', options.collection)
    logger.debug(u'Articles Meta API: %s, at port: %s', config.ARTICLE_META_THRIFT_DOMAIN, config.ARTICLE_META_THRIFT_PORT)
    if config.OPAC_PROC_MONGODB_USER and config.OPAC_PROC_MONGODB_PASS:
        logger.debug(u'Conexão e credenciais do banco: mongo://{username}:{password}@{host}:{port}/{db}'.format(**config.OPAC_PROC_MONGODB_SETTINGS))
    else:
        logger.debug(u'Conexão sem credenciais do banco: mongo://{host}:{port}/{db}'.format(**config.OPAC_PROC_MONGODB_SETTINGS))

    logger.debug(u'Nível do log: %s', options.logging_level)
    logger.debug(u'Arquivo de log: %s', options.logging_file)
    logger.debug(u'Número de processadores: %s', options.process)

    started = datetime.datetime.now()
    logger.info(u'Inicialização o processo: %s', started)

    bulk(options, pool)

    finished = datetime.datetime.now()
    logger.info(u'Finalização do processo: %s', finished)

    elapsed_time = str(finished - started)
    logger.info(u"Tempo total de processamento: %s sec.", elapsed_time)

    logger.info(U"Processamento finalizado com sucesso.")
    pool.close()
    pool.join()


def main(argv=sys.argv[1:]):
    """
    Processo para carregar dados desde o Article Meta para o MongoDB usado pelo OPAC
    """

    usage = u"""\
    %prog Este processamento coleta todos os Journal, Issues, Articles do Article meta,
    de uma determinada coleção, armazenando estes dados em um banco MongoDB,
    que serão exposto pelo OPAC.
    """

    def get_comma_separated_args(option, opt, value, parser):
        setattr(parser.values, option.dest, value.split(','))

    parser = optparse.OptionParser(
        textwrap.dedent(usage), version=u"version: 1.0")

    # Arquivo de log
    parser.add_option(
        '--logging_file',
        '-o',
        default=config.OPAC_PROC_LOG_FILE_PATH,
        help=u'Caminho absoluto do log file')

    # Nível do log
    parser.add_option(
        '--logging_level',
        '-l',
        default=config.OPAC_PROC_LOG_LEVEL,
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        help=u'Nível do log')

    # Coleção
    parser.add_option(
        '-c', '--collection',
        dest='collection',
        default=config.OPAC_PROC_COLLECTION,
        help=u'Acronimo da coleção. Por exemplo: spa, scl, col.')

    # Número de processos
    parser.add_option(
        '-p', '--num_process',
        dest='process',
        default=multiprocessing.cpu_count(),
        help=u'Número de processadores, o recomendado é utilizar a quantidade de processadores disponíveis na máquina.')

    # Serial
    parser.add_option(
        '-s', '--serial',
        dest='serial',
        action="store_true",
        help=u'Inícia o processamento em modo serial.')

    # Issns
    parser.add_option(
        '-i', '--issns',
        type='string',
        action='callback',
        dest='issns',
        callback=get_comma_separated_args)

    options, args = parser.parse_args(argv)

    config_logging(options.logging_level, options.logging_file)

    try:

        if options.serial:
            return serial(options)
        else:
            pool = Pool(options.process, init_worker)
            return run(options, pool)

    except KeyboardInterrupt:

        logger.info(u"Processamento interrompido pelo usuário.")

        if not options.serial:
            pool.terminate()
            pool.join()

if __name__ == '__main__':
    main(sys.argv)
