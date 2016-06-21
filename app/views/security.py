# coding=utf-8

from app.views import ModelViewWithAccess
from app.views.base import CycleReferenceValidator
from flask.ext.admin.contrib.sqla.fields import QuerySelectField
from flask.ext.admin.form import Select2Widget
from flask_admin.contrib.sqla import ModelView
from flask_babelex import lazy_gettext, gettext
from flask_login import current_user
from flask_security.utils import encrypt_password
from app.models.security import Organization
from sqlalchemy import func
from app.utils.security_util import is_super_admin, exclude_super_admin_roles
from app.views.formatter import organization_formatter
from app.utils import db_util
from wtforms import ValidationError
from wtforms import PasswordField


# Customized User model for SQL-Admin
class UserAdmin(ModelViewWithAccess):
    # Don't display the password on the list of Users
    column_exclude_list = list = ('password',)

    column_list = ('id', 'login', 'display', 'email', 'active',)

    """
    Disable delete of user(use de-active instead)
    """
    can_delete = False

    # Not working by now
    # column_editable_list = ('display', 'email', 'active')

    column_details_list = ('id', 'login', 'display', 'email', 'active', 'roles', 'locale', 'timezone')

    form_columns = ('login', 'display', 'email', 'locale', 'timezone', 'active', 'organization', 'roles',)

    column_filters = ('active',)

    column_searchable_list = ('login', 'display', 'email',)

    column_labels = dict(
        id=lazy_gettext('id'),
        login=lazy_gettext('Login Name'),
        display=lazy_gettext('Display'),
        email=lazy_gettext('Email'),
        active=lazy_gettext('Active'),
        roles=lazy_gettext('Role'),
        organization=lazy_gettext('Organization'),
    )

    # Don't include the standard password field when creating or editing a User (but see below)
    form_excluded_columns = ('password',)

    from app.models import User

    form_args = dict(
        active=dict(description=lazy_gettext('Un-check this checkbox to disable a user from login to the system')),
        locale=dict(label=lazy_gettext('Language'), query_factory=User.locale_filter),
        timezone=dict(label=lazy_gettext('Timezone'), query_factory=User.timezone_filter),
    )

    # Automatically display human-readable names for the current and available Roles when creating or editing a User
    column_auto_select_related = True

    # On the form for creating or editing a User, don't display a field corresponding to the model's password field.
    # There are two reasons for this. First, we want to encrypt the password before storing in the database. Second,
    # we want to use a password field (with the input masked) rather than a regular text field.
    def scaffold_form(self):
        # Start with the standard form as provided by Flask-Admin. We've already told Flask-Admin to exclude the
        # password field from this form.
        form_class = super(UserAdmin, self).scaffold_form()

        # Add a password field, naming it "password2" and labeling it "New Password".
        form_class.password2 = PasswordField(label=lazy_gettext('New Password'),
                                             description=lazy_gettext('Left blank if you don\'t want to change it, '
                                                                      'input the new password to change it'))
        return form_class

    def create_form(self, obj=None):
        form = super(ModelView, self).create_form(obj)
        if not is_super_admin():
            delattr(form, "organization")
        return form

    def edit_form(self, obj=None):
        form = super(ModelView, self).edit_form(obj)
        if not is_super_admin():
            delattr(form, "organization")
        return form

    # This callback executes when the user saves changes to a newly-created or edited User -- before the changes are
    # committed to the database.
    def on_model_change(self, form, model, is_created):
        # If the password field isn't blank...
        if not is_super_admin():
            super(UserAdmin, self).on_model_change(form, model, is_created)
        if len(model.password2):
            # ... then encrypt the new password prior to storing it in the database. If the password field is blank,
            # the existing password in the database will be retained.
            model.password = encrypt_password(model.password2)

    def get_query(self):
        """
        For cross organization super admin, return all the users
        For organization specify admin, only return users of it's own's organization
        :return:
        """
        return self.session.query(self.model) if is_super_admin() else super(UserAdmin, self).get_query()

    def get_count_query(self):
        """
        For cross organization super admin, return all the users
        For organization specify admin, only return users of it's own's organization
        :return:
        """
        return self.session.query(func.count('*')).select_from(self.model) \
            if is_super_admin() \
            else super(UserAdmin, self).get_count_query()


class RoleAdmin(ModelViewWithAccess):
    def is_accessible(self):
        return is_super_admin()

    def get_query(self):
        if not is_super_admin():
            return exclude_super_admin_roles(self.model.name, super(RoleAdmin, self).get_query())
        return super(RoleAdmin, self).get_query()

    def get_count_query(self):
        if not is_super_admin():
            return exclude_super_admin_roles(self.model.name, super(RoleAdmin, self).get_count_query())
        return super(RoleAdmin, self).get_count_query()

    def on_model_change(self, form, model, is_created):
        """Check whether the parent role is same as child role"""
        super(RoleAdmin, self).on_model_change(form, model, is_created)
        CycleReferenceValidator.validate(form, model, object_type='Role', parent='parent',
                                         children='sub_roles', is_created=is_created)

    column_list = ('id', 'name', 'description',)

    column_searchable_list = ('name', 'description', 'parent.name', 'parent.description')

    column_labels = dict(
        id=lazy_gettext('id'),
        name=lazy_gettext('Name'),
        description=lazy_gettext('Description'),
        users=lazy_gettext('User'),
        sub_roles=lazy_gettext('Sub Roles'),
        parent=lazy_gettext('Parent Role')
    )
    column_editable_list = ('description',)

    column_sortable_list = ('id', 'name', 'description')

    column_details_list = ('id', 'name', 'description', 'parent', 'sub_roles', 'users')


class OrganizationAdmin(ModelViewWithAccess):
    @property
    def can_create(self):
        return is_super_admin()

    @property
    def can_delete(self):
        return is_super_admin()

    def get_query(self):
        return self.session.query(self.model).filter(self.model.id == current_user.organization_id) \
            if not is_super_admin() else self.session.query(self.model)

    def get_count_query(self):
        return self.session.query(func.count('*')).filter(self.model.id == current_user.organization_id) \
            if not is_super_admin() else self.session.query(func.count('*'))

    column_list = ('id', 'name', 'description', 'parent', 'immediate_children',)

    column_sortable_list = ('id', 'name', 'description',)

    column_searchable_list = ('name', 'description', 'parent.name', 'parent.description', 'lft', 'right')

    column_labels = dict(
        id=lazy_gettext('id'),
        name=lazy_gettext('Name'),
        description=lazy_gettext('Description'),
        parent=lazy_gettext('Parent Organization'),
        lft=lazy_gettext('Left'),
        right=lazy_gettext('Right'),
        immediate_children=lazy_gettext('Immediate Children'),
        all_children=lazy_gettext('All Children'),
    )

    column_formatters = {
        'immediate_children': organization_formatter,
        'all_children': organization_formatter,
        'parent': organization_formatter
    }
    column_editable_list = ('description',)

    form_excluded_columns = ('lft', 'right',)

    form_extra_fields = {
        'parent': QuerySelectField(
            label=lazy_gettext('Parent Organization'),
            query_factory=lambda: Organization.query.all(),
            widget=Select2Widget(),
            allow_blank=False,
        )
    }

    def after_model_change(self, form, model, is_created):
        """
        :param form: form object from the UI
        :param model: model, when on after_model_change, it has got id field and necessary default value from DB.
        :param is_created: True if model was created, False if model was updated
        :return: None
        Update left and right field of all impacted organization vai raw sql, and also update left and right
        of the newly added organization to it's parent's current right and current right + 1
        """
        from sqlalchemy import text
        from app.database import DbInfo
        if is_created and getattr(form, "parent") is not None and getattr(form, "parent")._data is not None:
            # update all exiting node with right and left bigger than current parent's right - 1
            str_id = getattr(form, "parent").raw_data[0]
            int_id = int(str_id) if str_id is not None and len(str_id) > 0 else None
            parent = Organization.query.get(int_id) if int_id is not None else None
            if parent is not None:
                max_lft = parent.right - 1
                sql = text('UPDATE organization SET "right" = "right" + 2 WHERE "right" > {val};'
                           'UPDATE organization SET lft = lft + 2 WHERE lft > {val}'
                           .format(val=max_lft))
                db = DbInfo.get_db()

                # set left and right of the new object
                model.lft = max_lft + 1
                model.right = max_lft + 2
                db.engine.execute(sql)
                db_util.save_objects_commit(model)

    def on_model_change(self, form, model, is_created):
        """Check whether the parent organization or child organization is same as the value being edited"""
        super(OrganizationAdmin, self).on_model_change(form, model, is_created)
        if getattr(form, "parent") is None or getattr(form, "parent")._data is None:
            raise ValidationError(gettext('Please specify parent organization(creation of top level organization not allowed)'))
        CycleReferenceValidator.validate(form, model, object_type='Organization', parent='parent',
                                         children='all_children', is_created=is_created)

    def on_model_delete(self, model):
        if len(model.all_children) > 0:
            raise ValidationError(gettext('Can not delete an organization with child organisation exists'))

    column_details_list = ('id', 'name', 'description', 'lft', 'right', 'parent', 'immediate_children', 'all_children')
