from odoo import models, fields, api


class country(models.Model):
    _name = 'general.country'
    _description = 'general.country'

    country_id = fields.Char(
        string="Country ID", readonly=True, primary_key=True)
    country_name = fields.Char(string="Country Name")

    @api.model
    def create(self, vals):
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
    _description = 'general.state'

    state_id = fields.Char(string="State ID", readonly=True, primary_key=True)
    state_name = fields.Char(string="State Name")

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
    _description = 'general.city'

    city_id = fields.Char(string="City ID", readonly=True, primary_key=True)
    city_name = fields.Char(string="City Name")

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
    _description = 'general.district'

    district_id = fields.Char(string="District ID",
                              readonly=True, primary_key=True)
    district_name = fields.Char(string="District Name")

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
    _description = 'general.position'

    position_id = fields.Char(string="Position ID",
                              readonly=True, primary_key=True)
    position_name = fields.Char(string="Position Name")

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
    _description = 'general.department'

    department_id = fields.Char(
        string="Department ID", readonly=True, primary_key=True)
    department_name = fields.Char(string="Department Name")

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
    _description = 'general.menu'

    menuid = fields.Char(string="Menu ID", primary_key=True)
    menunm = fields.Char(string="Menu Name")
