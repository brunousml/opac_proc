# coding: utf-8
from xylose.scielodocument import Journal

from opac_proc.datastore.models import (
    ExtractJournal,
    TransformJournal,
    TransformCollection)
from opac_proc.transformers.base import BaseTransformer
from opac_proc.transformers.utils import trydate
from opac_proc.extractors.decorators import update_metadata

from opac_proc.web import config
from opac_proc.logger_setup import getMongoLogger

if config.DEBUG:
    logger = getMongoLogger(__name__, "DEBUG", "transform")
else:
    logger = getMongoLogger(__name__, "INFO", "transform")


class JournalTransformer(BaseTransformer):
    extract_model_class = ExtractJournal
    extract_model_instance = None

    transform_model_class = TransformJournal
    transform_model_instance = None

    def get_extract_model_instance(self, key):
        # retornamos uma instancia de ExtractJounal
        # buscando pela key (=issn)
        return self.extract_model_class.objects.get(code=key)

    @update_metadata
    def transform(self):
        xylose_source = self.clean_for_xylose()
        xylose_journal = Journal(xylose_source)

        # jid
        uuid = self.extract_model_instance.uuid
        self.transform_model_instance['uuid'] = uuid
        self.transform_model_instance['jid'] = uuid

        # collection
        transform_col = TransformCollection.objects.get(
            acronym__iexact=xylose_journal.collection_acronym)
        self.transform_model_instance['collection'] = transform_col.uuid

        # subject_categories
        if hasattr(xylose_journal, 'subject_areas'):
            self.transform_model_instance['subject_categories'] = xylose_journal.subject_areas

        # study_areas
        if hasattr(xylose_journal, 'wos_subject_areas'):
            self.transform_model_instance['study_areas'] = xylose_journal.wos_subject_areas

        # current_status
        if hasattr(xylose_journal, 'current_status'):
            self.transform_model_instance['current_status'] = xylose_journal.current_status

        # publisher_city
        if hasattr(xylose_journal, 'publisher_loc'):
            self.transform_model_instance['publisher_city'] = xylose_journal.publisher_loc

        # publisher_name
        if hasattr(xylose_journal, 'publisher_name') and len(xylose_journal.publisher_name) > 0:
            self.transform_model_instance['publisher_name'] = xylose_journal.publisher_name[0]

        # eletronic_issn
        if hasattr(xylose_journal, 'electronic_issn'):
            self.transform_model_instance['eletronic_issn'] = xylose_journal.electronic_issn

        # scielo_issn
        if hasattr(xylose_journal, 'scielo_issn'):
            self.transform_model_instance['scielo_issn'] = xylose_journal.scielo_issn

        # print_issn
        if hasattr(xylose_journal, 'print_issn'):
            self.transform_model_instance['print_issn'] = xylose_journal.print_issn

        # acronym
        if hasattr(xylose_journal, 'acronym'):
            self.transform_model_instance['acronym'] = xylose_journal.acronym

        # previous_title
        if hasattr(xylose_journal, 'previous_title'):
            self.transform_model_instance['previous_title'] = xylose_journal.previous_title

        # title
        if hasattr(xylose_journal, 'title'):
            self.transform_model_instance['title'] = xylose_journal.title

        # abbreviated_iso_title
        if hasattr(xylose_journal, 'abbreviated_iso_title'):
            self.transform_model_instance['title_iso'] = xylose_journal.abbreviated_iso_title

        # mission
        if hasattr(xylose_journal, 'mission'):
            missions = []
            for lang, des in xylose_journal.mission.items():
                missions.append({
                    'language': lang,
                    'description': des
                })
            self.transform_model_instance['mission'] = missions

        # timeline
        if hasattr(xylose_journal, 'status_history'):
            timelines = []
            for status in xylose_journal.status_history:
                timelines.append({
                    'reason': status[2],
                    'status': status[1],
                    'since': trydate(status[0]),
                })
            self.transform_model_instance['timeline'] = timelines

        # short_title
        if hasattr(xylose_journal, 'abbreviated_title'):
            self.transform_model_instance['short_title'] = xylose_journal.abbreviated_title

        # index_at
        if hasattr(xylose_journal, 'wos_citation_indexes'):
            self.transform_model_instance['index_at'] = xylose_journal.wos_citation_indexes

        # updated
        if hasattr(xylose_journal, 'update_date'):
            self.transform_model_instance['updated'] = trydate(xylose_journal.update_date)

        # created
        if hasattr(xylose_journal, 'creation_date'):
            self.transform_model_instance['created'] = trydate(xylose_journal.creation_date)

        # copyrighter
        if hasattr(xylose_journal, 'copyrighter'):
            self.transform_model_instance['copyrighter'] = xylose_journal.copyrighter

        # publisher_country
        if hasattr(xylose_journal, 'publisher_country') and len(xylose_journal.publisher_country) > 1:
            self.transform_model_instance['publisher_country'] = xylose_journal.publisher_country[1]

        # online_submission_url
        if hasattr(xylose_journal, 'online_submission_url'):
            self.transform_model_instance['online_submission_url'] = xylose_journal.online_submission_url

        # publisher_state
        if hasattr(xylose_journal, 'publisher_state'):
            self.transform_model_instance['publisher_state'] = xylose_journal.publisher_state

        # sponsors
        if hasattr(xylose_journal, 'sponsors'):
            self.transform_model_instance['sponsors'] = xylose_journal.sponsors

        # other_titles
        if hasattr(xylose_journal, 'other_titles') and xylose_journal.other_titles:
            other_titles = []
            for title in xylose_journal.other_titles:
                other_titles.append({
                    'title': title,
                    'category': "other",
                })
            self.transform_model_instance['other_titles'] = other_titles

        return self.transform_model_instance
