# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2009         Douglas S. Blank <doug.blank@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
# $Id$
#

""" Django/Gramps utilities """

#------------------------------------------------------------------------
#
# Python Modules
#
#------------------------------------------------------------------------
import locale

#------------------------------------------------------------------------
#
# Django Modules
#
#------------------------------------------------------------------------
from django.template import escape
from django.utils.safestring import mark_safe
from django.contrib.contenttypes.models import ContentType

#------------------------------------------------------------------------
#
# Gramps-Connect Modules
#
#------------------------------------------------------------------------
import web.grampsdb.models as models
import web.grampsdb.forms as forms
from web import libdjango
from web.djangodb import DjangoDb

#------------------------------------------------------------------------
#
# Gramps Modules
#
#------------------------------------------------------------------------
from Simple import SimpleTable, SimpleAccess, make_basic_stylesheet
import Utils
import DbState
import DateHandler
from gen.lib.date import Date as GDate, Today
import gen.lib
from gen.utils import get_birth_or_fallback, get_death_or_fallback
from gen.plug import BasePluginManager
from cli.grampscli import CLIManager

util_filters = ['person_event_table', 'person_name_table', 
                'person_attribute_table', 
                'person_address_table', 'person_note_table', 
                'person_gallery_table', 'person_internet_table', 
                'person_association_table', 'person_lds_table', 
                'person_reference_table',
                'family_children_table', 'family_event_table', 
                'family_attribute_table',
                'family_note_table', 'family_gallery_table', 
                'family_lds_table', 
                'nbsp', 'render']
#------------------------------------------------------------------------
#
# Module Constants
#
#------------------------------------------------------------------------
dji = libdjango.DjangoInterface()
_dd = DateHandler.displayer.display
_dp = DateHandler.parser.parse

def register_plugins():
    dbstate = DbState.DbState()
    climanager = CLIManager(dbstate, False) # don't load db
    climanager.do_reg_plugins()
    pmgr = BasePluginManager.get_instance()
    return pmgr

def probably_alive(handle):
    db = DjangoDb()
    person = db.get_person_from_handle(handle)
    return Utils.probably_alive(person, db)

def format_number(number, with_grouping=True):
    # FIXME: should be user's setting
    locale.setlocale(locale.LC_ALL, "en_US.utf8")
    return locale.format("%d", number, with_grouping)

def nbsp(string):
    """
    """
    if string:
        return string
    else:
        return mark_safe("&nbsp;")

class Table(object):
    """
    >>> table = Table()
    >>> table.columns("Col1", "Col2", "Col3")
    >>> table.row("1", "2", "3")
    >>> table.row("4", "5", "6")
    >>> table.get_html()
    """
    def __init__(self):
        self.db = DjangoDb()
        self.access = SimpleAccess(self.db)
        self.table = SimpleTable(self.access)
        class Doc(object):
            def __init__(self, doc):
                self.doc = doc
        # None is paperstyle, which is ignored:
        self.doc =  Doc(HtmlDoc.HtmlDoc(make_basic_stylesheet(Table={"set_width":95}), None))
        self.doc.doc._backend = HtmlBackend()
        # You can set elements id, class, etc:
        self.doc.doc.htmllist += [Html('div', style="overflow: auto; height:150px; background-color: white;")]

    def columns(self, *args):
        self.table.columns(*args)

    def row(self, *args):
        self.table.row(*[nbsp(arg) for arg in args])

    def link(self, object_type_name, handle):
        self.table.set_link_col((object_type_name, handle))

    def links(self, links):
        """
        A list of (object_type_name, handle) pairs, one per row.
        """
        self.table.set_link_col(links)

    def get_html(self):
        # The HTML writer escapes data:
        self.table.write(self.doc) # forces to htmllist
        # We have a couple of HTML bits that we want to unescape:
        return str(self.doc.doc.htmllist[0]).replace("&amp;nbsp;", "&nbsp;")

_ = lambda text: text

def render(formfield, action):
    retval = "error"
    fieldname = formfield.name # 'surname'
    if action == "view": # gets the unicode from model
        retval = str(getattr(formfield.form.model, fieldname))
    else: # renders as default
        retval = formfield.as_widget()
    return retval

def make_button(text, url):
    return """[<a href="%s">%s</a>]""" % (url, text)

def person_event_table(djperson, user):
    retval = ""
    table = Table()
    table.columns(_("Description"), 
                  _("Type"),
                  _("ID"),
                  _("Date"),
                  _("Place"),
                  _("Role"))
    if user.is_authenticated():
        obj_type = ContentType.objects.get_for_model(djperson)
        event_ref_list = models.EventRef.objects.filter(
            object_id=djperson.id, 
            object_type=obj_type).order_by("order")
        event_list = [(obj.ref_object, obj) for obj in event_ref_list]
        for (djevent, event_ref) in event_list:
            table.row(
                djevent.description,
                table.db.get_event_from_handle(djevent.handle),
                djevent.gramps_id, 
                display_date(djevent),
                get_title(djevent.place),
                str(event_ref.role_type))
    retval += table.get_html()
    if user.is_authenticated():
        retval += make_button(_("Add event"), "/person/%s/event/add" % djperson.handle)
    return retval

def person_name_table(djperson, user):
    print "person_name_table", djperson, user
    retval = ""
    table = Table()
    table.columns(_("Name"), 
                  _("Type"),
                  _("Group As"),
                  _("Source"),
                  _("Note Preview"))
    if user.is_authenticated():
        links = []
        for name in djperson.name_set.all().order_by("order"):
            obj_type = ContentType.objects.get_for_model(name)
            sourceq = dji.SourceRef.filter(object_type=obj_type,
                                           object_id=name.id).count() > 0
            note_refs = dji.NoteRef.filter(object_type=obj_type,
                                           object_id=name.id)
            note = ""
            if note_refs.count() > 0:
                try:
                    note = dji.Note.get(id=note_refs[0].object_id).text[:50]
                except:
                    note = None
            table.row(make_name(name, user),
                      str(name.name_type),
                      name.group_as,
                      ["No", "Yes"][sourceq],
                      note)
            links.append(('URL', "/person/%s/name/%s" % 
                          (name.person.handle, name.order)))
        table.links(links)
    retval += table.get_html()
    if user.is_authenticated():
        retval += make_button(_("Add name"), "/person/%s/name/add" % djperson.handle)
    return retval

def source_table(obj, user, action, url=None, *args):
    retval = ""
    table = Table()
    table.columns(_("ID"), 
                  _("Title"),
                  _("Author"),
                  _("Page"))
    if user.is_authenticated():
        obj_type = ContentType.objects.get_for_model(obj)
        source_refs = dji.SourceRef.filter(object_type=obj_type,
                                           object_id=obj.id)
        for source_ref in source_refs:
            source = table.db.get_source_from_handle(source_ref.ref_object.handle)
            table.row(source,
                      source_ref.ref_object.title,
                      source_ref.ref_object.author,
                      source_ref.page,
                      )
    retval += table.get_html()
    if user.is_authenticated() and url and action != "edit":
        retval += make_button(_("Add source"), url % args)
    return retval

def person_attribute_table(djperson, user):
    retval = ""
    table = Table()
    table.columns(_("Type"), 
                  _("Value"),
                  )
    if user.is_authenticated():
        obj_type = ContentType.objects.get_for_model(djperson)
        attributes = dji.Attribute.filter(object_type=obj_type,
                                          object_id=djperson.id)
        for attribute in attributes:
            table.row(attribute.attribute_type.name,
                      attribute.value)
    retval += table.get_html()
    if user.is_authenticated():
        retval += make_button(_("Add attribute"), "/person/%s/attribute/add" % djperson.handle)
    return retval

def person_address_table(djperson, user):
    retval = ""
    table = Table()
    table.columns(_("Date"), 
                  _("Address"),
                  _("City"),
                  _("State"),
                  _("Country"))
    if user.is_authenticated():
        for address in djperson.address_set.all().order_by("order"):
            locations = address.location_set.all().order_by("order")
            for location in locations:
                table.row(display_date(address),
                          location.street,
                          location.city,
                          location.state,
                          location.country)
    retval += table.get_html()
    if user.is_authenticated():
        retval += make_button(_("Add address"), "/person/%s/address/add" % djperson.handle)
    return retval

def person_note_table(djperson, user):
    retval = ""
    table = Table()
    table.columns(
        _("ID"),
        _("Type"),
        _("Note"))
    if user.is_authenticated():
        obj_type = ContentType.objects.get_for_model(djperson)
        note_refs = dji.NoteRef.filter(object_type=obj_type,
                                       object_id=djperson.id)
        for note_ref in note_refs:
            note = table.db.get_note_from_handle(
                note_ref.ref_object.handle)
            table.row(table.db.get_note_from_handle(note.handle),
                      str(note_ref.ref_object.note_type),
                      note_ref.ref_object.text[:50])
    retval += table.get_html()
    if user.is_authenticated():
        retval += make_button(_("Add note"), "/person/%s/note/add" % djperson.handle)
    return retval

def person_gallery_table(djperson, user):
    retval = ""
    table = Table()
    table.columns(_("Name"), 
                  _("Type"),
                  )
    retval += table.get_html()
    if user.is_authenticated():
        retval += make_button(_("Add gallery"), "/person/%s/gallery/add" % djperson.handle)
    return retval

def person_internet_table(djperson, user):
    retval = ""
    table = Table()
    table.columns(_("Type"),
                  _("Path"),
                  _("Description"))
    if user.is_authenticated():
        urls = dji.Url.filter(person=djperson)
        for url in urls:
            table.row(str(url.url_type),
                      url.path,
                      url.desc)
    retval += table.get_html()
    if user.is_authenticated():
        retval += make_button(_("Add internet"), "/person/%s/internet/add" % djperson.handle)
    return retval

def person_association_table(djperson, user):
    retval = ""
    table = Table()
    table.columns(_("Name"), 
                  _("ID"),
                  _("Association"))
    if user.is_authenticated():
        gperson = table.db.get_person_from_handle(djperson.handle)
        associations = gperson.get_person_ref_list()
        for association in associations:
            table.row()
    retval += table.get_html()
    if user.is_authenticated():
        retval += make_button(_("Add association"), "/person/%s/association/add" % djperson.handle)
    return retval

def person_lds_table(djperson, user):
    retval = ""
    table = Table()
    table.columns(_("Type"), 
                  _("Date"),
                  _("Status"),
                  _("Temple"),
                  _("Place"))
    if user.is_authenticated():
        obj_type = ContentType.objects.get_for_model(djperson)
        ldss = djperson.lds_set.all().order_by("order")
        for lds in ldss:
            table.row(str(lds.lds_type),
                      display_date(lds),
                      str(lds.status),
                      lds.temple,
                      get_title(lds.place))
    retval += table.get_html()
    if user.is_authenticated():
        retval += make_button(_("Add LDS"), "/person/%s/lds/add" % djperson.handle)
    return retval

def person_reference_table(djperson, user):
    retval = ""
    table = Table()
    table.columns(_("Type"), 
                  _("ID"),
                  _("Name"))
    if user.is_authenticated():
        references = dji.PersonRef.filter(ref_object=djperson)
        for reference in references:
            table.row(str(reference.ref_object),
                      reference.ref_object.gramps_id,
                      make_name(reference.ref_object.name_set, user))
    return table.get_html()

def family_children_table(djfamily, user):
    retval = ""
    table = Table()
    table.columns(
        _("#"),
        _("ID"),
        _("Name"),
        _("Gender"),
        _("Paternal"),
        _("Maternal"),
        _("Birth Date"),
        )
    #if user.is_authenticated():
    #for djfamily:
    #    table.row("test")
    return table.get_html()

def family_event_table(djfamily, user):
    retval = ""
    table = Table()
    table.columns(
        _("Description"),
        _("Type"),
        _("ID"),
        _("Date"),
        _("Place"),
        _("Role"),
        )
    table.row("test")
    return table.get_html()

def family_source_table(djfamily, user):
    retval = ""
    table = Table()
    table.columns(
        _("ID"),
        _("Type"),
        _("Author"),
        _("Page"),
        )
    table.row("test")
    return table.get_html()

def family_attribute_table(djfamily, user):
    retval = ""
    table = Table()
    table.columns(
        _("Type"),
        _("Value"),
        )
    table.row("test")
    return table.get_html()

def family_note_table(djfamily, user):
    retval = ""
    table = Table()
    table.columns(
        _("Type"),
        _("Preview"),
        )
    table.row("test")
    return table.get_html()

def family_gallery_table(djfamily, user):
    retval = ""
    table = Table()
    table.columns(
        _("Column"),
        )
    table.row("test")
    return table.get_html()

def family_lds_table(djfamily, user):
    retval = ""
    table = Table()
    table.columns(
        _("Type"),
        _("Date"),
        _("Status"),
        _("Temple"),
        _("Place"),
        )
    table.row("test")
    return table.get_html()

## FIXME: these dji function wrappers just use the functions
## written for the import/export. Can be done much more directly.

def get_title(place):
    if place:
        return place.title
    else:
        return ""

def person_get_birth_date(person):
    db = DjangoDb()
    event = get_birth_or_fallback(db, person)
    if event:
        return event.date
    return None

def person_get_death_date(person):
    db = DjangoDb()
    event = get_death_or_fallback(db, person)
    if event:
        return event.date
    return None

def display_date(obj):
    date_tuple = dji.get_date(obj)
    if date_tuple:
        gdate = GDate()
        gdate.unserialize(date_tuple)
        return _dd(gdate)
    else:
        return ""

def person_get_event(person, event_type=None):
    event_ref_list = dji.get_event_ref_list(person)
    if event_type:
        index = libdjango.lookup_role_index(event_type, event_ref_list)
        if index >= 0:
            event_handle = event_ref_list[index][3]
            # (False, [], [], u'b2cfa6cdec87392cf3b', (1, u'Primary'))
            # WARNING: the same object can be referred to more than once
            objs = models.EventRef.objects.filter(ref_object__handle=event_handle)
            if objs.count() > 0:
                return display_date(objs[0].ref_object)
            else:
                return ""
        else:
            return ""
    else:
        retval = [[obj.ref_object for obj in 
                   models.EventRef.objects.filter(ref_object__handle=event_handle[3])] 
                  for event_handle in event_ref_list]
        return [j for i in retval for j in i]

def make_name(name, user=None):
    if isinstance(name, models.Name):
        surname = name.surname.strip()
        if not surname:
            surname = "[Missing]"
        if user.is_authenticated():
            return "%s, %s" % (surname, name.first_name)
        else:
            if probably_alive(name.person.handle):
                return "%s, %s" % (surname, "[Living]")
            else:
                return "%s, %s" % (surname, name.first_name)
    elif isinstance(name, forms.NameForm):
        surname = name.model.surname.strip()
        if not surname:
            surname = "[Missing]"
        if user.is_authenticated():
            return "%s, %s" % (surname, name.model.first_name)
        else:
            if probably_alive(name.model.person.handle):
                return "%s, %s" % (surname, "[Living]")
            else:
                return "%s, %s" % (surname, name.model.first_name)
    elif isinstance(name, gen.lib.Person): # name is a gen.lib.Person
        person = name
        name = person.get_primary_name()
        if name is None:
            return "[No preferred name]"
        else:
            return "%s, %s" % (name.get_surname(), name.get_first_name())
    else: # no name
        return ""

register_plugins()

# works after registering plugins:
import HtmlDoc 
from libhtmlbackend import HtmlBackend
from libhtml import Html
