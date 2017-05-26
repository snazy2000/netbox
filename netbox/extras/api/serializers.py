from __future__ import unicode_literals

from django.core.exceptions import ObjectDoesNotExist

from rest_framework import serializers

from dcim.api.serializers import NestedDeviceSerializer, NestedRackSerializer, NestedSiteSerializer
from dcim.models import Device, Rack, Site
from extras.models import (
    ACTION_CHOICES, ExportTemplate, Graph, GRAPH_TYPE_CHOICES, ImageAttachment, TopologyMap, UserAction,
)
from users.api.serializers import NestedUserSerializer
from utilities.api import ChoiceFieldSerializer, ContentTypeFieldSerializer


#
# Graphs
#

class GraphSerializer(serializers.ModelSerializer):
    type = ChoiceFieldSerializer(choices=GRAPH_TYPE_CHOICES)

    class Meta:
        model = Graph
        fields = ['id', 'type', 'weight', 'name', 'source', 'link']


class WritableGraphSerializer(serializers.ModelSerializer):

    class Meta:
        model = Graph
        fields = ['id', 'type', 'weight', 'name', 'source', 'link']


class RenderedGraphSerializer(serializers.ModelSerializer):
    embed_url = serializers.SerializerMethodField()
    embed_link = serializers.SerializerMethodField()
    type = ChoiceFieldSerializer(choices=GRAPH_TYPE_CHOICES)

    class Meta:
        model = Graph
        fields = ['id', 'type', 'weight', 'name', 'embed_url', 'embed_link']

    def get_embed_url(self, obj):
        return obj.embed_url(self.context['graphed_object'])

    def get_embed_link(self, obj):
        return obj.embed_link(self.context['graphed_object'])


#
# Export templates
#

class ExportTemplateSerializer(serializers.ModelSerializer):

    class Meta:
        model = ExportTemplate
        fields = ['id', 'content_type', 'name', 'description', 'template_code', 'mime_type', 'file_extension']


#
# Topology maps
#

class TopologyMapSerializer(serializers.ModelSerializer):
    site = NestedSiteSerializer()

    class Meta:
        model = TopologyMap
        fields = ['id', 'name', 'slug', 'site', 'device_patterns', 'description']


class WritableTopologyMapSerializer(serializers.ModelSerializer):

    class Meta:
        model = TopologyMap
        fields = ['id', 'name', 'slug', 'site', 'device_patterns', 'description']


#
# Image attachments
#

class ImageAttachmentSerializer(serializers.ModelSerializer):
    parent = serializers.SerializerMethodField()

    class Meta:
        model = ImageAttachment
        fields = ['id', 'parent', 'name', 'image', 'image_height', 'image_width', 'created']

    def get_parent(self, obj):

        # Static mapping of models to their nested serializers
        if isinstance(obj.parent, Device):
            serializer = NestedDeviceSerializer
        elif isinstance(obj.parent, Rack):
            serializer = NestedRackSerializer
        elif isinstance(obj.parent, Site):
            serializer = NestedSiteSerializer
        else:
            raise Exception("Unexpected type of parent object for ImageAttachment")

        return serializer(obj.parent, context={'request': self.context['request']}).data


class WritableImageAttachmentSerializer(serializers.ModelSerializer):
    content_type = ContentTypeFieldSerializer()

    class Meta:
        model = ImageAttachment
        fields = ['id', 'content_type', 'object_id', 'name', 'image']

    def validate(self, data):

        # Validate that the parent object exists
        try:
            data['content_type'].get_object_for_this_type(id=data['object_id'])
        except ObjectDoesNotExist:
            raise serializers.ValidationError(
                "Invalid parent object: {} ID {}".format(data['content_type'], data['object_id'])
            )

        return data


#
# User actions
#

class UserActionSerializer(serializers.ModelSerializer):
    user = NestedUserSerializer()
    action = ChoiceFieldSerializer(choices=ACTION_CHOICES)

    class Meta:
        model = UserAction
        fields = ['id', 'time', 'user', 'action', 'message']
