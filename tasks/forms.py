from django import forms
from .models import Task
from processes.models import Stage


class TaskAdminForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        process_instance = None

        # 1. если редактируем существующую задачу
        if self.instance.pk and self.instance.process_instance_id:
            process_instance = self.instance.process_instance

        # 2. если форма отправлена (POST) и пользователь уже выбрал process_instance
        elif self.data.get("process_instance"):
            try:
                process_instance_id = int(self.data.get("process_instance"))
                from processes.models import ProcessInstance
                process_instance = ProcessInstance.objects.get(id=process_instance_id)
            except (ValueError, ProcessInstance.DoesNotExist):
                process_instance = None

        # 3. если нашли process_instance — фильтруем stage
        if process_instance:
            self.fields["stage"].queryset = Stage.objects.filter(
                process=process_instance.process
            )
        else:
            # пока process_instance не выбран — этапов нет
            self.fields["stage"].queryset = Stage.objects.none()
