from __future__ import unicode_literals

from django import forms
from django.db.models import Count

from dcim.formfields import MACAddressFormField
from extras.forms import CustomFieldBulkEditForm, CustomFieldForm, CustomFieldFilterForm
from tenancy.forms import TenancyForm
from tenancy.models import Tenant
from utilities.forms import (
    APISelect, BootstrapMixin, BulkEditForm, BulkEditNullBooleanSelect, ChainedModelChoiceField, ComponentForm,
    ExpandableNameField, FilterChoiceField, SlugField,
)
from .models import Cluster, ClusterGroup, ClusterType, VirtualMachine, VMInterface


#
# Cluster types
#

class ClusterTypeForm(BootstrapMixin, forms.ModelForm):
    slug = SlugField()

    class Meta:
        model = ClusterType
        fields = ['name', 'slug']


#
# Cluster groups
#

class ClusterGroupForm(BootstrapMixin, forms.ModelForm):
    slug = SlugField()

    class Meta:
        model = ClusterGroup
        fields = ['name', 'slug']


#
# Clusters
#

class ClusterForm(BootstrapMixin, CustomFieldForm):

    class Meta:
        model = Cluster
        fields = ['name', 'type', 'group']


class ClusterCSVForm(forms.ModelForm):
    type = forms.ModelChoiceField(
        queryset=ClusterType.objects.all(),
        to_field_name='name',
        help_text='Name of cluster type',
        error_messages={
            'invalid_choice': 'Invalid cluster type name.',
        }
    )
    group = forms.ModelChoiceField(
        queryset=ClusterGroup.objects.all(),
        to_field_name='name',
        required=False,
        help_text='Name of cluster group',
        error_messages={
            'invalid_choice': 'Invalid cluster group name.',
        }
    )

    class Meta:
        fields = ['name', 'type', 'group']


class ClusterFilterForm(BootstrapMixin, CustomFieldFilterForm):
    model = Cluster
    q = forms.CharField(required=False, label='Search')
    group = FilterChoiceField(
        queryset=ClusterGroup.objects.annotate(filter_count=Count('clusters')),
        to_field_name='slug',
        null_option=(0, 'None'),
        required=False,
    )
    type = FilterChoiceField(
        queryset=ClusterType.objects.annotate(filter_count=Count('clusters')),
        to_field_name='slug',
        required=False,
    )


#
# Virtual Machines
#

class VirtualMachineForm(BootstrapMixin, TenancyForm, CustomFieldForm):
    cluster_group = forms.ModelChoiceField(
        queryset=ClusterGroup.objects.all(),
        required=False,
        widget=forms.Select(
            attrs={'filter-for': 'cluster', 'nullable': 'true'}
        )
    )
    cluster = ChainedModelChoiceField(
        queryset=Cluster.objects.all(),
        chains=(
            ('group', 'cluster_group'),
        ),
        widget=APISelect(
            api_url='/api/virtualization/clusters/?group_id={{cluster_group}}'
        )
    )

    class Meta:
        model = VirtualMachine
        fields = ['name', 'cluster_group', 'cluster', 'tenant', 'platform', 'vcpus', 'memory', 'disk', 'comments']

    def __init__(self, *args, **kwargs):

        # Initialize helper selector
        instance = kwargs.get('instance')
        if instance.pk and instance.cluster is not None:
            initial = kwargs.get('initial', {}).copy()
            initial['cluster_group'] = instance.cluster.group
            kwargs['initial'] = initial

        super(VirtualMachineForm, self).__init__(*args, **kwargs)


class VirtualMachineCSVForm(forms.ModelForm):
    cluster = forms.ModelChoiceField(
        queryset=Cluster.objects.all(),
        to_field_name='name',
        help_text='Name of parent cluster',
        error_messages={
            'invalid_choice': 'Invalid cluster name.',
        }
    )

    class Meta:
        fields = ['cluster', 'name', 'tenant', 'platform', 'vcpus', 'memory', 'disk', 'comments']


class VirtualMachineBulkEditForm(BootstrapMixin, CustomFieldBulkEditForm):
    pk = forms.ModelMultipleChoiceField(queryset=VirtualMachine.objects.all(), widget=forms.MultipleHiddenInput)
    cluster = forms.ModelChoiceField(queryset=Cluster.objects.all(), required=False, label='Cluster')
    tenant = forms.ModelChoiceField(queryset=Tenant.objects.all(), required=False)

    class Meta:
        nullable_fields = ['tenant']


class VirtualMachineFilterForm(BootstrapMixin, CustomFieldFilterForm):
    model = VirtualMachine
    q = forms.CharField(required=False, label='Search')
    cluster_group = FilterChoiceField(
        queryset=ClusterGroup.objects.all(),
        to_field_name='slug',
        null_option=(0, 'None'),
    )
    cluster_id = FilterChoiceField(
        queryset=Cluster.objects.annotate(filter_count=Count('virtual_machines')),
        label='Cluster'
    )


#
# VM interfaces
#

class VMInterfaceForm(BootstrapMixin, forms.ModelForm):

    class Meta:
        model = VMInterface
        fields = ['virtual_machine', 'name', 'enabled', 'mac_address', 'mtu', 'description']
        widgets = {
            'virtual_machine': forms.HiddenInput(),
        }


class VMInterfaceCreateForm(ComponentForm):
    name_pattern = ExpandableNameField(label='Name')
    enabled = forms.BooleanField(required=False)
    mtu = forms.IntegerField(required=False, min_value=1, max_value=32767, label='MTU')
    mac_address = MACAddressFormField(required=False, label='MAC Address')
    description = forms.CharField(max_length=100, required=False)

    def __init__(self, *args, **kwargs):

        # Set interfaces enabled by default
        kwargs['initial'] = kwargs.get('initial', {}).copy()
        kwargs['initial'].update({'enabled': True})

        super(VMInterfaceCreateForm, self).__init__(*args, **kwargs)


class VMInterfaceBulkEditForm(BootstrapMixin, BulkEditForm):
    pk = forms.ModelMultipleChoiceField(queryset=VMInterface.objects.all(), widget=forms.MultipleHiddenInput)
    virtual_machine = forms.ModelChoiceField(queryset=VirtualMachine.objects.all(), widget=forms.HiddenInput)
    enabled = forms.NullBooleanField(required=False, widget=BulkEditNullBooleanSelect)
    mtu = forms.IntegerField(required=False, min_value=1, max_value=32767, label='MTU')
    description = forms.CharField(max_length=100, required=False)

    class Meta:
        nullable_fields = ['mtu', 'description']
