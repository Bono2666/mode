from odoo import models, fields, api


class country(models.Model):
    _name = 'general.country'
    _description = 'general.country'

    countryid = fields.Char(default=lambda self: self.env['ir.sequence'].next_by_code(
        'general.country'), string="Country ID")
    countrynm = fields.Char(string="Country Name")


class state(models.Model):
    _name = 'general.state'
    _description = 'general.state'

    stateid = fields.Char(default=lambda self: self.env['ir.sequence'].next_by_code(
        'general.state'), string="State ID")
    statenm = fields.Char(string="State Name")


class city(models.Model):
    _name = 'general.city'
    _description = 'general.city'

    cityid = fields.Char(default=lambda self: self.env['ir.sequence'].next_by_code(
        'general.city'), string="City ID")
    citynm = fields.Char(string="City Name")


class region(models.Model):
    _name = 'general.region'
    _description = 'general.region'

    regionid = fields.Char(default=lambda self: self.env['ir.sequence'].next_by_code(
        'general.region'), string="Region ID")
    regionnm = fields.Char(string="Region Name")


class position(models.Model):
    _name = 'general.position'
    _description = 'general.position'

    positionid = fields.Char(default=lambda self: self.env['ir.sequence'].next_by_code(
        'general.position'), string="Position ID")
    positionnm = fields.Char(string="Position Name")


class department(models.Model):
    _name = 'general.department'
    _description = 'general.department'

    departmentid = fields.Char(default=lambda self: self.env['ir.sequence'].next_by_code(
        'general.department'), string="Department ID")
    departmentnm = fields.Char(string="Department Name")


class menu(models.Model):
    _name = 'general.menu'
    _description = 'general.menu'

    menuid = fields.Char(string="Menu ID")
    menunm = fields.Char(string="Menu Name")
