# from odoo import http


# class Autosave(http.Controller):
#     @http.route('/autosave/autosave', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/autosave/autosave/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('autosave.listing', {
#             'root': '/autosave/autosave',
#             'objects': http.request.env['autosave.autosave'].search([]),
#         })

#     @http.route('/autosave/autosave/objects/<model("autosave.autosave"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('autosave.object', {
#             'object': obj
#         })

