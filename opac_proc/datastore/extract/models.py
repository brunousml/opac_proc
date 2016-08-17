# coding: utf-8
from __future__ import unicode_literals

from mongoengine import (
    DynamicDocument,
    StringField,
    IntField,
    DateTimeField,
    ListField,
    EmbeddedDocumentField,
    EmbeddedDocumentListField,
    ReferenceField,
    BooleanField,
    URLField,
    DynamicDocument
)


class BaseExtractionMixin(object):
    # campos relacionados a extração
    extraction_start_at = DateTimeField()
    extraction_finish_at = DateTimeField()
    extraction_complete = BooleanField(required=True, default=False)
    extraction_error_msg = StringField()

    # soft delete
    is_deleted = BooleanField(required=True, default=False)

    @property
    def is_extracting(self):
        """
        Retorna True se o documento esta em fase de extração
        """
        return not self.transform_complete

    @property
    def has_errors(self):
        """
        Retorna True se o documento poduziu algum error
        na fase de extração.
        """
        if hasattr(self, 'extraction_error_msg'):
            return self.extraction_error_msg.strip() == ""
        else:
            return False

    # reset:
    def reset(self):
        """
        Restaura os campos de controle do documento
        ao ponto anterior à extração
        """
        self.extraction_start_at = None
        self.extraction_finish_at = None
        self.extraction_complete = False
        self.extraction_error_msg = ''


class ExtractCollection(BaseExtractionMixin, DynamicDocument):
    acronym = StringField(required=True, unique=True)

    meta = {
        'collection': 'e_collection'
    }


class ExtractJournal(BaseExtractionMixin, DynamicDocument):
    meta = {
        'collection': 'e_journal'
    }


class ExtractIssue(BaseExtractionMixin, DynamicDocument):
    meta = {
        'collection': 'e_issue'
    }


class ExtractArticle(BaseExtractionMixin, DynamicDocument):
    meta = {
        'collection': 'e_article'
    }