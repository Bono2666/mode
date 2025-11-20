# from odoo import http


# class DisableAutosave(http.Controller):
#     @http.route('/disable_autosave/disable_autosave', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/disable_autosave/disable_autosave/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('disable_autosave.listing', {
#             'root': '/disable_autosave/disable_autosave',
#             'objects': http.request.env['disable_autosave.disable_autosave'].search([]),
#         })

#     @http.route('/disable_autosave/disable_autosave/objects/<model("disable_autosave.disable_autosave"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('disable_autosave.object', {
#             'object': obj
#         })

