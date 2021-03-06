import datetime

from django.db import models
from django.db.models import Case, Count, F, Max, Q, Value, When
from django.utils.timezone import now


class DomainCheckQuerySet(models.QuerySet):
    """Custom queryset to filter and annotate domain checks."""

    def active(self):
        return self.filter(is_active=True)

    def stale(self, cutoff=datetime.timedelta(hours=1)):
        end_time = now() - cutoff
        return self.annotate(
            last_check=Max('checkresult__checked_on')
        ).filter(
            Q(last_check__lt=end_time) | Q(last_check__isnull=True))

    def status(self, cutoff=datetime.timedelta(hours=1)):
        start_time = now() - cutoff
        ping = Q(checkresult__checked_on__gte=start_time)
        success = Q(
            checkresult__checked_on__gte=start_time,
            checkresult__status_code__range=(200, 299))
        return self.annotate(
            last_check=Max('checkresult__checked_on'),
            successes=Count(Case(When(success, then=1))),
            pings=Count(Case(When(ping, then=1))),
        ).annotate(
            success_rate=F('successes') * 100.0 / F('pings')
        ).annotate(
            status=Case(
                When(success_rate__gt=90, then=Value('good')),
                When(success_rate__range=(75, 90), then=Value('fair')),
                When(success_rate__lt=75, then=Value('poor')),
                When(success_rate__isnull=True, then=Value('unknown')),
                output_field=models.CharField())
        )


class DomainCheck(models.Model):
    """Configured website check."""

    PROTOCOL_HTTP = 'http'
    PROTOCOL_HTTPS = 'https'

    PROTOCOL_CHOICES = (
        (PROTOCOL_HTTP, 'HTTP'),
        (PROTOCOL_HTTPS, 'HTTPS'),
    )

    METHOD_GET = 'get'
    METHOD_POST = 'post'
    METHOD_CHOICES = (
        (METHOD_GET, 'GET'),
        (METHOD_POST, 'POST'),
    )

    domain = models.CharField(max_length=253)
    path = models.CharField(max_length=1024)
    protocol = models.CharField(
        max_length=5, choices=PROTOCOL_CHOICES, default=PROTOCOL_HTTP)
    method = models.CharField(
        max_length=4, choices=METHOD_CHOICES, default=METHOD_GET)
    is_active = models.BooleanField(default=True)

    objects = DomainCheckQuerySet.as_manager()

    def __str__(self):
        return '{method} {url}'.format(
            method=self.get_method_display(), url=self.url)

    @property
    def url(self):
        return '{protocol}://{domain}{path}'.format(
            protocol=self.protocol, domain=self.domain, path=self.path)


class CheckResult(models.Model):
    """Result of a status check on a website."""

    domain_check = models.ForeignKey(DomainCheck)
    checked_on = models.DateTimeField()
    status_code = models.PositiveIntegerField(null=True)
    response_time = models.FloatField(null=True)
    response_body = models.TextField(default='')
