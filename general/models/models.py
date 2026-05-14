from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ChangePasswordPreferences(models.TransientModel):
    _name = 'general.password_preferences'
    _description = 'Change Password Preferences'

    user_id = fields.Many2one('res.users', string="User", required=True)

    # Tahap 1
    old_password = fields.Char(string="Old Password", required=True)
    is_verified = fields.Boolean(default=False)  # Penanda tahap

    # Tahap 2
    new_password = fields.Char(string="New Password")
    confirm_password = fields.Char(string="New Password (Confirmation)")

    def action_verify_old_password(self):
        """Langkah 1: Verifikasi Password Lama"""
        self.ensure_one()
        try:
            # Mengecek apakah password lama benar
            self.user_id.sudo()._check_credentials(self.old_password, {})
            self.is_verified = True
            # Tetap buka wizard (jangan tutup)
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'general.password_preferences',
                'view_mode': 'form',
                'res_id': self.id,
                'target': 'new',
            }
        except Exception:
            raise UserError(
                _("Incorrect Password, try again or contact an administrator to reset your password."))

    def action_update_password(self):
        """Langkah 2: Update Password Baru"""
        self.ensure_one()
        if not self.is_verified:
            raise UserError(
                _("Please verify your old password first."))

        if self.new_password != self.confirm_password:
            raise UserError(_("New password and confirmation do not match!"))

        if len(self.new_password) < 6:
            raise UserError(_("Password must be at least 6 characters."))

        self.user_id.sudo().write({'password': self.new_password})

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Succeed'),
                'message': _('Your password has been updated.'),
                'type': 'success',
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }


class MyPreferences(models.TransientModel):
    _name = 'general.preferences'
    _description = 'Change My Profile'

    user_id = fields.Many2one(
        'res.users', default=lambda self: self.env.user, readonly=True)
    name = fields.Char(related='user_id.name',
                       string="User Name", readonly=True)
    image_1920 = fields.Image(
        related='user_id.image_1920', string="Photo Profile", readonly=False)
    login = fields.Char(related='user_id.login',
                        string="Email/Login", readonly=True)

    def action_open_change_password(self):
        """Memanggil wizard ganti password yang sudah dibuat sebelumnya"""
        return {
            'name': 'Change Password',
            'type': 'ir.actions.act_window',
            'res_model': 'general.password_preferences',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_user_id': self.env.user.id},
        }

    def action_save_preferences(self):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Succeed'),
                'message': _('Your preferences has been updated.'),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }


class ChangePasswordWizard(models.TransientModel):
    _name = 'general.password'
    _description = 'Change Password'

    user_id = fields.Many2one('res.users', string="User", required=True)
    new_password = fields.Char(string="New Password", required=True)
    confirm_password = fields.Char(
        string="Confirmation Password", required=True)

    def action_update_password(self):
        self.ensure_one()
        # 1. Validasi: Cek apakah password sama
        if self.new_password != self.confirm_password:
            raise UserError(_("New password and confirmation do not match!"))

        # 2. Validasi: Minimal panjang password (opsional)
        if len(self.new_password) < 6:
            raise UserError(_("Password must be at least 6 characters."))

        # 3. Update password ke model res.users secara Sudo
        self.user_id.sudo().write({'password': self.new_password})

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Succeed'),
                'message': _('Password has been updated for user %s') % self.user_id.name,
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }


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
                        import lxml.etree as etree
                        doc = etree.fromstring(res['views'][view_type]['arch'])
                        doc.set('create', '0')  # Paksa tombol New jadi hilang
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

    def action_back_kanban(self):
        self.ensure_one()
        return {
            'name': self._description,
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'kanban,form',
            'views': [(False, 'kanban'), (False, 'form')],
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
        if self._name == "general.custom_users" and self.is_edit:
            self.user_id.sudo().write({'name': self.name})
            self.user_id.sudo().write({'login': self.login})
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
        if self._name == "general.custom_users":
            self.user_id.sudo().unlink()
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

    def action_password(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Change Password',
            'res_model': 'general.password',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_user_id': self.user_id.id},
        }


class country(models.Model):
    _name = 'general.country'
    _inherit = ['navigation.mixin']
    _description = 'Countries'
    _rec_name = 'country_name'
    _menu_code = 'country'

    country_id = fields.Char(string="Country ID", readonly=True)
    country_name = fields.Char(string="Country Name")
    is_edit = fields.Boolean(default=False)

    @api.model
    def create(self, vals):
        is_admin = self.env.user.has_group('base.group_system')
        if not is_admin:
            access = self.env['general.auth'].sudo().search([
                ('custom_user_id.user_id', '=', self.env.uid),
                ('menu_id.menu_id', '=', self._menu_code)
            ], limit=1)

            if not access or not access.create:  # 'create' adalah nama field di model auth Anda
                raise UserError(
                    _("You do not have access rights to create new data in this menu!"))

        if isinstance(vals, list):
            for v in vals:
                if not v.get('country_id'):
                    v['country_id'] = self.env['ir.sequence'].next_by_code(
                        'general.country.sequence') or '/'
            return super(country, self).create(vals)
        if not vals.get('country_id'):
            vals['country_id'] = self.env['ir.sequence'].next_by_code(
                'general.country.sequence') or '/'
        return super(country, self).create(vals)


class state(models.Model):
    _name = 'general.state'
    _inherit = ['navigation.mixin']
    _description = 'States'
    _rec_name = 'state_name'
    _menu_code = 'state'

    state_id = fields.Char(string="State ID", readonly=True)
    state_name = fields.Char(string="State Name")
    is_edit = fields.Boolean(default=False)

    @api.model
    def create(self, vals):
        if isinstance(vals, list):
            for v in vals:
                if not v.get('state_id'):
                    v['state_id'] = self.env['ir.sequence'].next_by_code(
                        'general.state.sequence') or '/'
            return super(state, self).create(vals)
        if not vals.get('state_id'):
            vals['state_id'] = self.env['ir.sequence'].next_by_code(
                'general.state.sequence') or '/'
        return super(state, self).create(vals)


class city(models.Model):
    _name = 'general.city'
    _inherit = ['navigation.mixin']
    _description = 'Cities'
    _rec_name = 'city_name'
    _menu_code = 'city'

    city_id = fields.Char(string="City ID", readonly=True)
    city_name = fields.Char(string="City Name")
    is_edit = fields.Boolean(default=False)

    @api.model
    def create(self, vals):
        if isinstance(vals, list):
            for v in vals:
                if not v.get('city_id'):
                    v['city_id'] = self.env['ir.sequence'].next_by_code(
                        'general.city.sequence') or '/'
            return super(city, self).create(vals)
        if not vals.get('city_id'):
            vals['city_id'] = self.env['ir.sequence'].next_by_code(
                'general.city.sequence') or '/'
        return super(city, self).create(vals)


class district(models.Model):
    _name = 'general.district'
    _inherit = ['navigation.mixin']
    _description = 'Districts'
    _rec_name = 'district_name'
    _menu_code = 'district'

    district_id = fields.Char(string="District ID", readonly=True)
    district_name = fields.Char(string="District Name")
    is_edit = fields.Boolean(default=False)

    @api.model
    def create(self, vals):
        if isinstance(vals, list):
            for v in vals:
                if not v.get('district_id'):
                    v['district_id'] = self.env['ir.sequence'].next_by_code(
                        'general.district.sequence') or '/'
            return super(district, self).create(vals)
        if not vals.get('district_id'):
            vals['district_id'] = self.env['ir.sequence'].next_by_code(
                'general.district.sequence') or '/'
        return super(district, self).create(vals)


class position(models.Model):
    _name = 'general.position'
    _inherit = ['navigation.mixin']
    _description = 'Position'
    _rec_name = 'position_name'
    _menu_code = 'position'

    position_id = fields.Char(string="Position ID", readonly=True)
    position_name = fields.Char(string="Position Name")
    is_edit = fields.Boolean(default=False)

    @api.model
    def create(self, vals):
        if isinstance(vals, list):
            for v in vals:
                if not v.get('position_id'):
                    v['position_id'] = self.env['ir.sequence'].next_by_code(
                        'general.position.sequence') or '/'
            return super(position, self).create(vals)
        if not vals.get('position_id'):
            vals['position_id'] = self.env['ir.sequence'].next_by_code(
                'general.position.sequence') or '/'
        return super(position, self).create(vals)


class department(models.Model):
    _name = 'general.department'
    _inherit = ['navigation.mixin']
    _description = 'Departments'
    _rec_name = 'department_name'
    _menu_code = 'department'

    department_id = fields.Char(string="Department ID", readonly=True)
    department_name = fields.Char(string="Department Name")
    is_edit = fields.Boolean(string="Is Edit?", default=False)

    @api.model
    def create(self, vals):
        if isinstance(vals, list):
            for v in vals:
                if not v.get('department_id'):
                    v['department_id'] = self.env['ir.sequence'].next_by_code(
                        'general.department.sequence') or '/'
            return super(department, self).create(vals)
        if not vals.get('department_id'):
            vals['department_id'] = self.env['ir.sequence'].next_by_code(
                'general.department.sequence') or '/'
        return super(department, self).create(vals)


class menu(models.Model):
    _name = 'general.menu'
    _description = 'Menus'
    _rec_name = 'menu_name'

    menu_id = fields.Char(string="Menu ID")
    menu_name = fields.Char(string="Menu Name")
    parent_menu = fields.Char(string="Parent Menu")
    is_parent = fields.Boolean(string="Is Parent Menu?", default=False)


class home(models.Model):
    _name = 'general.home'
    _description = 'Home'

    name = fields.Char()


class custom_users(models.Model):
    _name = 'general.custom_users'
    _inherit = ['navigation.mixin']
    _description = 'Users'
    _menu_code = 'custom_users'

    custom_user_id = fields.Char(string="User Id", readonly=True)
    name = fields.Char(string="Name", required=True)
    login = fields.Char(string="Email/Login", required=True)
    password = fields.Char(string="Password", required=True)
    position = fields.Many2one(
        comodel_name='general.position', string='Job Position')
    is_edit = fields.Boolean(default=False)

    # Field untuk menyimpan referensi ke record asli res.users
    user_id = fields.Many2one(
        'res.users', string="Related Users", readonly=True)
    image_1920 = fields.Image(string="Photo Profile",
                              related='user_id.image_1920', readonly=False)
    avatar_128 = fields.Image(related='user_id.avatar_128', readonly=False)
    custom_login_date = fields.Datetime(
        related='user_id.login_date', string="Latest Authentication", readonly=True)
    menu_ids = fields.One2many(
        'general.auth', 'custom_user_id', string="User Authentication", domain=[('is_parent', '=', False)])

    @api.model
    def create(self, vals):
        if isinstance(vals, list):
            for v in vals:
                if not v.get('custom_user_id'):
                    v['custom_user_id'] = self.env['ir.sequence'].next_by_code(
                        'general.custom_users_sequence') or '/'
            return super(custom_users, self).create(vals)
        if not vals.get('custom_user_id'):
            vals['custom_user_id'] = self.env['ir.sequence'].next_by_code(
                'general.custom_users_sequence') or '/'

        # 1. Buat user baru di model res.users
        user_vals = {
            'name': vals.get('name'),
            'login': vals.get('login'),
            'password': vals.get('password'),
            # Grup default
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id])]
        }
        new_user = self.env['res.users'].create(user_vals)

        # Pastikan email partner user terisi dari login (login biasanya berupa email)
        if new_user.partner_id and vals.get('login'):
            new_user.partner_id.sudo().write({'email': vals.get('login')})

        # 2. Simpan referensi ID-nya ke model kustom ini
        vals['user_id'] = new_user.id
        return super(custom_users, self).create(vals)

    def write(self, vals):
        # Trigger fields that need to be synced to User and Partner
        sync_fields = ['name', 'login', 'image_1920']

        if any(field in vals for field in sync_fields):
            for record in self:
                user_vals = {}
                partner_vals = {}

                if 'name' in vals:
                    user_vals['name'] = vals['name']
                    partner_vals['name'] = vals['name']  # Partner sync

                if 'login' in vals:
                    user_vals['login'] = vals['login']
                    # Usually login is the email
                    partner_vals['email'] = vals['login']

                if 'image_1920' in vals:
                    img = vals['image_1920']
                    user_vals.update({'image_1920': img, 'avatar_128': img})
                    partner_vals.update(
                        {'image_1920': img, 'avatar_128': img})  # Partner sync

                # Update User
                if user_vals and record.user_id:
                    record.user_id.sudo().write(user_vals)

                    # Update Partner via the User's partner_id
                    if partner_vals:
                        record.user_id.partner_id.sudo().write(partner_vals)

        return super(custom_users, self).write(vals)

    def copy(self, default=None):
        default = dict(default or {})

        copied_count = self.search_count(
            [('login', '=like', "Copy of {}%".format(self.login))])

        # Kalau tidak ada
        if not copied_count:
            # Copy of training odoo
            new_login = "Copy of {}".format(self.login)
            new_name = "Copy of {}".format(self.name)

        # # Kalau ada
        else:
            # Copy of training odoo (jumlah ada berapa)
            new_login = "Copy of {} ({})".format(self.login, copied_count)
            new_name = "Copy of {} ({})".format(self.name, copied_count)

        default['login'] = new_login
        default['name'] = new_name
        return super(custom_users, self).copy(default)

    def unlink(self):
        # Hapus user terkait di res.users saat menghapus record ini
        for record in self:
            if record.user_id:
                record.user_id.sudo().unlink()
        return super(custom_users, self).unlink()


class auth(models.Model):
    _name = 'general.auth'
    _description = 'Authentications'

    custom_user_id = fields.Many2one(
        'general.custom_users', string='User', ondelete='cascade', index=True)
    user_id = fields.Many2one(
        'res.users', related='custom_user_id.user_id', string="User ID", readonly=True)
    menu_id = fields.Many2one('general.menu', string="Menu", domain=[
                              ('is_parent', '=', False)])
    is_parent = fields.Boolean(string="Is Parent Menu?", default=False)
    can_create = fields.Boolean(default=False)
    can_update = fields.Boolean(default=False)
    can_delete = fields.Boolean(default=False)
    can_submit = fields.Boolean(default=False)
    can_send = fields.Boolean(default=False)
    can_confirm = fields.Boolean(default=False)
    can_invoicing = fields.Boolean(default=False)
    can_receive = fields.Boolean(default=False)
    can_billing = fields.Boolean(default=False)

    @api.model
    def create(self, vals):
        # Cek duplikasi
        existing_record = self.env['general.auth'].search([
            ('custom_user_id', '=', vals.get('custom_user_id')),
            ('menu_id', '=', vals.get('menu_id'))
        ], limit=1)

        if existing_record:
            raise UserError(
                _("This user already has access settings for the selected menu."))

        record = super(auth, self).create(vals)
        if not self.env.context.get('skip_menu_refresh'):
            record._refresh_related_user_menu_access()
        return record

    def write(self, vals):
        res = super(auth, self).write(vals)
        if not self.env.context.get('skip_menu_refresh'):
            self._refresh_related_user_menu_access()
        return res

    def unlink(self):
        users = self.mapped('custom_user_id.user_id')
        res = super(auth, self).unlink()
        if users and not self.env.context.get('skip_menu_refresh'):
            users._refresh_custom_menu_access()
        return res

    def _refresh_related_user_menu_access(self):
        users = self.mapped('custom_user_id.user_id')
        if users:
            users._refresh_custom_menu_access()


class ResUsers(models.Model):
    """
    Model to handle hiding specific menu items for certain users.
    """
    _inherit = 'res.users'

    hide_menu_ids = fields.Many2many(
        'ir.ui.menu', string="Hidden Menu",
        store=True, help='Select menu items that need to '
                         'be hidden to this user.')

    def _refresh_custom_menu_access(self):
        general_menu_model = self.env['general.menu']
        auth_model = self.env['general.auth'].sudo()
        ir_ui_menu_model = self.env['ir.ui.menu'].sudo()
        custom_user_model = self.env['general.custom_users'].sudo()

        for user in self:
            # Cari semua menu yang membatasi user ini
            restricted_menus = ir_ui_menu_model.search([
                ('restrict_user_ids', 'in', user.id)
            ])

            # Hapus relasi Many2many pada model ir.ui.menu
            if restricted_menus:
                restricted_menus.write({
                    'restrict_user_ids': [(3, user.id)]
                })

            # Kosongkan field Many2many di sisi res.users (jika ada)
            user.sudo().write({
                'hide_menu_ids': [(5, 0, 0)]
            })

            # Hapus semua entri parent auto-generated, lalu hitung ulang
            auth_model.with_context(skip_menu_refresh=True).search([
                ('custom_user_id.user_id', '=', user.id),
                ('is_parent', '=', True)
            ]).unlink()

            all_menus = general_menu_model.search([])
            menu_obj = auth_model.search(
                [('custom_user_id.user_id', '=', user.id)])
            existing_menu_ids = [menu.menu_id.id for menu in menu_obj]

            repeated = True
            while repeated:
                repeated = False
                for menu in all_menus:
                    if menu.id in existing_menu_ids:
                        parent_menu_id = menu.parent_menu
                        if parent_menu_id:
                            parent_menu = general_menu_model.search(
                                [('menu_id', '=', parent_menu_id)], limit=1)
                            parent_menu_id = parent_menu.id if parent_menu else False
                        if parent_menu_id and parent_menu_id not in existing_menu_ids:
                            existing_parent = auth_model.search([
                                ('custom_user_id.user_id', '=', user.id),
                                ('menu_id', '=', parent_menu_id)
                            ], limit=1)
                            if not existing_parent:
                                repeated = True
                                auth_model.with_context(skip_menu_refresh=True).create({
                                    'custom_user_id': custom_user_model.search(
                                        [('user_id', '=', user.id)], limit=1).id,
                                    'menu_id': parent_menu_id,
                                    'is_parent': True,
                                    'can_create': False,
                                    'can_update': False,
                                    'can_delete': False,
                                })

                menu_obj = auth_model.search(
                    [('custom_user_id.user_id', '=', user.id)])
                existing_menu_ids = [menu.menu_id.id for menu in menu_obj]

            for menu in all_menus:
                if menu.id not in existing_menu_ids:
                    menu_records = ir_ui_menu_model.search(
                        [('name', '=', menu.menu_name)])
                    if menu_records:
                        menu_records.write({
                            'restrict_user_ids': [(4, user.id)]
                        })

    @api.model
    def _update_last_login(self):
        """
        Metode ini dipanggil otomatis oleh Odoo setiap kali user berhasil login.
        """
        super(ResUsers, self)._update_last_login()
        self.env.user._refresh_custom_menu_access()


class IrUiMenu(models.Model):
    """
    Model to restrict the menu for specific users.
    """
    _inherit = 'ir.ui.menu'

    restrict_user_ids = fields.Many2many(
        'res.users', string="Restricted Users",
        help='Users restricted from accessing this menu.')

    @api.returns('self')
    def _filter_visible_menus(self):
        """
        Override to filter out menus restricted for current user.
        Applies only to the current user context.
        """

        menus = super(IrUiMenu, self)._filter_visible_menus()

        # Allow system admin to see everything
        if self.env.user.has_group('base.group_system'):
            return menus

        return menus.filtered(
            lambda m: self.env.user not in m.restrict_user_ids)
