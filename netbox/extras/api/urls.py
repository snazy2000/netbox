from rest_framework import routers

from . import views


class ExtrasRootView(routers.APIRootView):
    """
    Extras API root view
    """
    def get_view_name(self):
        return 'Extras'


router = routers.DefaultRouter()
router.APIRootView = ExtrasRootView

# Graphs
router.register(r'graphs', views.GraphViewSet)

# Export templates
router.register(r'export-templates', views.ExportTemplateViewSet)

# Topology maps
router.register(r'topology-maps', views.TopologyMapViewSet)

# Image attachments
router.register(r'image-attachments', views.ImageAttachmentViewSet)

# Recent activity
router.register(r'recent-activity', views.RecentActivityViewSet)

app_name = 'extras-api'
urlpatterns = router.urls
