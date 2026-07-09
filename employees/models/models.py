from odoo import models, fields, api

import ast
import lxml.etree as etree


def _inject_m2o_no_open_create(doc, model_name, env):
    """Inject no_open=True and no_create=True into all Many2one <field> nodes."""
    Model = env.get(model_name)
    if Model is None:
        return
    field_defs = Model.fields_get()
    for field_el in doc.iter('field'):
        field_name = field_el.get('name')
        if not field_name or field_name not in field_defs:
            continue
        if field_defs[field_name].get('type') != 'many2one':
            continue
        existing = field_el.get('options', '{}')
        try:
            opts = ast.literal_eval(existing)
        except (ValueError, SyntaxError):
            opts = {}
        opts.setdefault('no_open', True)
        opts.setdefault('no_create', True)
        field_el.set('options', repr(opts))


class NavigationMixin(models.AbstractModel):
    _name = 'navigation.mixin'
    _description = 'Mixin for General Navigation'

    model_description = fields.Char(compute='_compute_model_description')
    user_can_read = fields.Boolean(compute='_compute_custom_permissions')
    user_can_create = fields.Boolean(
        compute='_compute_custom_permissions', store=False)
    user_can_update = fields.Boolean(compute='_compute_custom_permissions')
    user_can_delete = fields.Boolean(compute='_compute_custom_permissions')

    @api.model
    def get_views(self, views, options=None):
        res = super().get_views(views, options=options)

        # Pengecekan Admin
        if not self.env.user.has_group('base.group_system'):
            # Cari akses di tabel kustom
            access = self.env['general.auth'].sudo().search([
                ('custom_user_id.user_id', '=', self.env.uid),
                ('menu_id.menu_id', '=', self._menu_code)
            ], limit=1)

            # Jika tidak punya akses create, hapus kemampuan create dari arsitektur view
            if not access or not access.can_create:
                for view_type in ['list', 'form']:
                    if view_type in res['views']:
                        doc = etree.fromstring(res['views'][view_type]['arch'])
                        doc.set('create', '0')  # Paksa tombol New jadi hilang
                        res['views'][view_type]['arch'] = etree.tostring(
                            doc, encoding='unicode')

        # Global: inject no_open/no_create on all Many2one fields
        for view_type in ['form', 'list', 'tree', 'kanban', 'search']:
            arch = res.get('views', {}).get(view_type, {}).get('arch')
            if arch:
                doc = etree.fromstring(arch)
                _inject_m2o_no_open_create(doc, self._name, self.env)
                res['views'][view_type]['arch'] = etree.tostring(
                    doc, encoding='unicode')

        return res

    @api.depends_context('uid')
    def _compute_custom_permissions(self):
        is_admin = self.env.user.has_group('base.group_system')

        # 2. Jika Admin, berikan akses penuh secara otomatis
        if is_admin:
            for record in self:
                record.user_can_read = True
                record.user_can_create = True
                record.user_can_update = True
                record.user_can_delete = True
            return

        menu_code = getattr(self, '_menu_code', False)

        access = self.env['general.auth'].sudo().search([
            ('custom_user_id.user_id', '=', self.env.uid),
            ('menu_id.menu_id', '=', menu_code)
        ], limit=1)

        for record in self:
            if access:
                record.user_can_read = True
                record.user_can_create = access.can_create
                record.user_can_update = access.can_update
                record.user_can_delete = access.can_delete
            else:
                record.user_can_read = False
                record.user_can_create = False
                record.user_can_update = False
                record.user_can_delete = False

    def _compute_model_description(self):
        for record in self:
            record.model_description = self._description

    def action_back(self):
        self.ensure_one()
        return {
            'name': self._description,
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'tree,form',
            'views': [(False, 'tree'), (False, 'form')],
            'target': 'main',
            'context': self.env.context,
        }

    def action_edit(self):
        self.ensure_one()
        self.write({'is_edit': True})

        view_id = self.env['ir.ui.view'].sudo().search([
            ('model', '=', self._name),
            ('type', '=', 'form')
        ], limit=1).id

        return {
            'type': 'ir.actions.act_window',
            'name': self._description,
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'views': [(view_id, 'form')],
            'target': 'current',
        }

    def action_save(self):
        self.ensure_one()
        self.write({'is_edit': False})

        view_id = self.env['ir.ui.view'].sudo().search([
            ('model', '=', self._name),
            ('type', '=', 'form')
        ], limit=1).id

        return {
            'type': 'ir.actions.act_window',
            'name': self._description,
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'views': [(view_id, 'form')],
            'target': 'current',
        }

    def action_delete(self):
        self.ensure_one()
        self.unlink()

        return {
            'name': self._description,
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'tree,form',
            'views': [(False, 'tree'), (False, 'form')],
            'target': 'main',
            'context': self.env.context,
        }


class employees(models.Model):
    _name = 'employees.employees'
    _inherit = ['navigation.mixin']
    _description = 'Employees'
    _rec_name = 'employee_name'
    _menu_code = 'employee'

    employee_id = fields.Char(string="Employee ID", readonly=True)
    employee_name = fields.Char(string="Employee Name")
    position_id = fields.Many2one(
        comodel_name='general.position', string='Job Position')
    department_id = fields.Many2one(
        comodel_name='general.department', string='Department')
    sales_code = fields.Char(string="Sales Code")
    is_edit = fields.Boolean(default=False)

    @api.model
    def create(self, vals):
        if isinstance(vals, list):
            for v in vals:
                if not v.get('employee_id'):
                    v['employee_id'] = self.env['ir.sequence'].next_by_code(
                        'employees.employees.sequence')
            return super(employees, self).create(vals)
        if not vals.get('employee_id'):
            vals['employee_id'] = self.env['ir.sequence'].next_by_code(
                'employees.employees.sequence')
        return super(employees, self).create(vals)
