"""Strict core14 Note legend identities; no journal bodies or renderer fields."""
from typing import Annotated,Literal
from pydantic import Field,model_validator
from .selective_models import Model
from .map_models import MapNamed

NoteKey=Annotated[str,Field(pattern=r'^N[1-9][0-9]{0,14}$',description='Exact alias from this Scene/level/revision; never a global Note identifier.')]
NoteUUID=Annotated[str,Field(pattern=r'^Scene\.[A-Za-z0-9_-]{1,128}\.Note\.[A-Za-z0-9_-]{1,128}$')]
NoteKeys=Annotated[list[NoteKey],Field(min_length=1,max_length=100,description='Distinct exact returned aliases; requires expected_revision and section=notes.')]


class NoteJournalIdentity(MapNamed):
    journal_uuid: Annotated[str,Field(pattern=r'^JournalEntry\.[A-Za-z0-9_-]{1,128}$')]


class NotePageIdentity(MapNamed):
    page_uuid: Annotated[str,Field(pattern=r'^JournalEntry\.[A-Za-z0-9_-]{1,128}\.JournalEntryPage\.[A-Za-z0-9_-]{1,128}$')]


class MapNoteEntry(Model):
    kind: Literal['note']
    note_uuid: NoteUUID
    key: NoteKey
    x: int|float=Field(description='Finite source Scene X coordinate, not original image pixels.')
    y: int|float=Field(description='Finite source Scene Y coordinate, not original image pixels.')
    level_id: Annotated[str,Field(pattern=r'^[A-Za-z0-9_-]{1,128}$')]
    label: str|None=Field(max_length=256,description='Authorized plain untrusted label; null for denied linked content.')
    label_truncated: bool
    target_status: Literal['unlinked','missing_entry','denied_entry','missing_page','denied_page','linked_entry','linked_page']
    journal: NoteJournalIdentity|None
    page: NotePageIdentity|None

    @model_validator(mode='after')
    def target_consistency(self):
        if self.target_status in ('unlinked','missing_entry','denied_entry'):
            if self.journal is not None or self.page is not None:raise ValueError('Unavailable target cannot expose identity')
        elif self.journal is None:raise ValueError('Readable entry identity required')
        if (self.target_status=='linked_page')!=(self.page is not None):raise ValueError('Wrong page status')
        if self.page and not self.page.page_uuid.startswith(self.journal.journal_uuid+'.JournalEntryPage.'):
            raise ValueError('Wrong page owner')
        if self.target_status in ('denied_entry','denied_page') and self.label is not None:raise ValueError('Denied target label')
        if self.label_truncated and (self.label is None or len(self.label)!=256):raise ValueError('Wrong clipped label marker')
        return self
