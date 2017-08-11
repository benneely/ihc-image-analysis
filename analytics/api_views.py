from analytics import serializers, models
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from lungmap_client import lungmap_utils
from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.core.files.base import ContentFile
from lung_map_utils import utils
import numpy as np
import pandas as pd
import pickle
# noinspection PyPackageRequirements
import cv2
import django_filters


class UserList(generics.ListAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    queryset = User.objects.all()
    serializer_class = serializers.UserSerializer


class UserDetail(generics.RetrieveAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    queryset = User.objects.all()
    serializer_class = serializers.UserSerializer


class ImageSetList(generics.ListAPIView):
    queryset = models.ImageSet.objects.all()
    serializer_class = serializers.ImageSetSerializer


class ImageSetDetail(generics.RetrieveAPIView):
    """
    Get an image
    """

    queryset = models.ImageSet.objects.all()
    serializer_class = serializers.ImageSetDetailSerializer


class AnatomyByProbeList(generics.RetrieveAPIView):
    queryset = models.Probe.objects.all()
    serializer_class = serializers.AnatomySerializer


# noinspection PyClassHasNoInit
class LungmapImageFilter(django_filters.rest_framework.FilterSet):
    class Meta:
        model = models.Image
        fields = ['experiment']


class LungmapImageList(generics.ListAPIView):
    """
    List all images.
    """

    queryset = models.Image.objects.all()
    serializer_class = serializers.LungmapImageSerializer
    filter_class = LungmapImageFilter


class AnatomyList(generics.RetrieveAPIView):
    """
    List all images.
    """

    queryset = models.Anatomy.objects.all()
    serializer_class = serializers.AnatomyModelSerializer


class LungmapImageDetail(generics.RetrieveAPIView):
    """
    Get an image
    """

    queryset = models.Image.objects.all()
    serializer_class = serializers.LungmapImageSerializer

    def retrieve(self, request, *args, **kwargs):
        serializer_context = {
            'request': request
        }
        img = self.get_object()
        try:
            with transaction.atomic():
                if img.image_orig_sha1 is None or img.image_orig_sha1 == '':
                    suf, sha1, suf_jpeg = lungmap_utils.get_image_from_s3(img.s3key)
                    img.image_orig = suf
                    img.image_orig_sha1 = sha1
                    img.image_jpeg = suf_jpeg
                    img.save()
                serializer = serializers.LungmapImageSerializer(
                    img,
                    context=serializer_context
                )
                return Response(
                    serializer.data,
                    status=status.HTTP_200_OK
                )
        except Exception as e:
            if hasattr(e, 'messages'):
                return Response(data={'detail': e.messages}, status=400)
            return Response(data={'detail': e}, status=400)


class TrainAModelCreate(generics.CreateAPIView):
    queryset = models.TrainedModel.objects.all()
    serializer_class = serializers.TrainedModelCreateSerializer

    def create(self, request, *args, **kwargs):
        try:
            print(request.data['imageset'])
            image_set = models.ImageSet.objects.get(id=request.data['imageset'])
            images = image_set.image_set.prefetch_related('subregion_set')
            training_data = []
            for image in images:
                sub_regions = image.subregion_set.all()
                if len(sub_regions) > 0:
                    # TODO: don't use file path in case you're moving to S3 or something else
                    # noinspection PyUnresolvedReferences
                    sub_img = cv2.imread(image.image_orig.path)
                    # noinspection PyUnresolvedReferences
                    sub_img = cv2.cvtColor(sub_img, cv2.COLOR_BGR2HSV)
                    for subregion in sub_regions:
                        points = subregion.points.all()
                        this_mask = np.empty((0, 2), dtype='int')
                        for point in points:
                            this_mask = np.append(this_mask, [[point.x, point.y]], axis=0)
                        training_data.append(
                            utils.generate_custom_features(
                                hsv_img_as_numpy=sub_img,
                                polygon_points=this_mask,
                                label=subregion.anatomy.name
                            )
                        )

            pipe = utils.pipe
            training_data = pd.DataFrame(training_data)
            pipe.fit(training_data.drop('label', axis=1), training_data['label'])
            content = pickle.dumps(pipe)
            pickled_model = ContentFile(content)
            pickled_model.name = image_set.image_set_name + '.pkl'
            final = models.TrainedModel(imageset=image_set, model_object=pickled_model)
            final.save()

            return Response(
                serializers.TrainedModelSerializer(final).data,
                status=status.HTTP_201_CREATED
            )
        except Exception as e:  # catch any exception to rollback changes
            if hasattr(e, 'messages'):
                return Response(data={'detail': e.messages}, status=400)

            return Response(data={'detail': e}, status=400)


# noinspection PyUnusedLocal
@api_view(['GET'])
def get_image_jpeg(request, pk):
    """
    Get JPEG version of a single image
    """
    image = get_object_or_404(models.Image, pk=pk)
    if image.image_jpeg.name == '':
        content = {'image_jpeg': 'image not yet cached'}
        return Response(content, status=status.HTTP_404_NOT_FOUND)
    else:
        return HttpResponse(image.image_jpeg, content_type='image/jpeg')


class ClassifySubRegion(generics.GenericAPIView):
    queryset = models.Image.objects.all()
    serializer_class = serializers.ClassifyPointsSerializer

    # noinspection PyMethodMayBeStatic
    def post(self, request):
        points = request.data['points']
        for point in points:
            print(point)
        return Response(request.data, status=status.HTTP_200_OK)


# noinspection PyClassHasNoInit
class LungmapSubRegionFilter(django_filters.rest_framework.FilterSet):
    class Meta:
        model = models.Subregion
        fields = ['image']


class SubregionList(generics.ListCreateAPIView):
    # permission_classes = (permissions.IsAuthenticated,)
    queryset = models.Subregion.objects.all()
    serializer_class = serializers.SubregionSerializer
    filter_class = LungmapSubRegionFilter
    # TODO: wrap this view in an atomic transaction, can cause serious bugs
    # TODO: handling this with UI conditionals at the moment, but should be here as well


class SubregionDetail(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    queryset = models.Subregion.objects.all()
    serializer_class = serializers.SubregionSerializer


class ImagesetSubRegionCountList(generics.ListAPIView):
    queryset = models.ImageSet.objects.all()
    serializer_class = serializers.CountImages


class SubregionAnatomyAggregation(generics.ListAPIView):
    queryset = models.Subregion.objects.all()
    serializer_class = serializers.SubregionAnatomyAggregationSerializer

    def get_queryset(self):
        return models.Subregion.objects.select_related().values(
            'anatomy__name', 'anatomy_id').annotate(count=Count('anatomy_id'))
