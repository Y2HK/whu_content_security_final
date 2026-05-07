<template>
  <div class="page-wrap">
    <el-card>
      <template #header>
        <div class="header-row">
          <span>{{ isTeacher ? '学生管理' : '我的信息' }}</span>
          <div v-if="isTeacher" class="actions">
            <el-button type="primary" @click="openCreate">新增学生</el-button>
          </div>
        </div>
      </template>

      <el-form v-if="isTeacher" inline>
        <el-form-item label="批量导入 CSV">
          <el-upload :show-file-list="false" :http-request="uploadBatch">
            <el-button>上传 CSV</el-button>
          </el-upload>
        </el-form-item>
        <el-form-item>
          <el-button plain @click="downloadTemplate">下载示例 CSV</el-button>
        </el-form-item>
      </el-form>

      <el-table :data="students" v-loading="loading" border>
        <el-table-column prop="student_no" label="学号" />
        <el-table-column prop="name" label="姓名" />
        <el-table-column prop="class_name" label="班级" />
        <el-table-column prop="face_image_path" label="人脸图片路径" min-width="220" />
        <el-table-column label="操作" :width="isTeacher ? 320 : 150">
          <template #default="scope">
            <el-button v-if="isTeacher" size="small" @click="openEdit(scope.row)">编辑</el-button>
            <el-upload :show-file-list="false" :http-request="(options) => uploadFace(scope.row, options)">
              <el-button size="small" type="primary" plain>上传人脸</el-button>
            </el-upload>
            <el-button v-if="isTeacher" size="small" type="danger" @click="removeStudent(scope.row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="dialogMode === 'create' ? '新增学生' : '编辑学生'" width="480px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="学号"><el-input v-model="form.student_no" /></el-form-item>
        <el-form-item label="姓名"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="班级"><el-input v-model="form.class_name" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import request from '../api/request'
import { useAuthStore } from '../stores/auth'

const authStore = useAuthStore()
const isTeacher = computed(() => authStore.user?.role === 'teacher')
const loading = ref(false)
const dialogVisible = ref(false)
const dialogMode = ref('create')
const students = ref([])
const currentStudentId = ref(null)
const form = reactive({
  student_no: '',
  name: '',
  class_name: '',
})

const resetForm = () => {
  form.student_no = ''
  form.name = ''
  form.class_name = ''
  currentStudentId.value = null
}

const fetchStudents = async () => {
  loading.value = true
  try {
    const { data } = await request.get('/students')
    students.value = data.data
  } finally {
    loading.value = false
  }
}

const openCreate = () => {
  dialogMode.value = 'create'
  resetForm()
  dialogVisible.value = true
}

const openEdit = (row) => {
  dialogMode.value = 'edit'
  currentStudentId.value = row.student_id
  form.student_no = row.student_no
  form.name = row.name
  form.class_name = row.class_name
  dialogVisible.value = true
}

const submitForm = async () => {
  try {
    if (dialogMode.value === 'create') {
      await request.post('/students', form)
      ElMessage.success('新增成功')
    } else {
      await request.put(`/students/${currentStudentId.value}`, form)
      ElMessage.success('更新成功')
    }
    dialogVisible.value = false
    await fetchStudents()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '保存失败')
  }
}

const removeStudent = async (row) => {
  await ElMessageBox.confirm(`确认删除学生 ${row.name} 吗？`, '提示', { type: 'warning' })
  await request.delete(`/students/${row.student_id}`)
  ElMessage.success('删除成功')
  await fetchStudents()
}

const uploadFace = async (row, options) => {
  const formData = new FormData()
  formData.append('file', options.file)
  try {
    await request.post(`/students/${row.student_id}/face`, formData)
    ElMessage.success('上传成功')
    await fetchStudents()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '上传失败')
  }
}

const uploadBatch = async (options) => {
  const formData = new FormData()
  formData.append('file', options.file)
  try {
    await request.post('/students/batch', formData)
    ElMessage.success('批量导入完成')
    await fetchStudents()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '导入失败')
  }
}

const downloadTemplate = () => {
  window.open('/sample-students.csv', '_blank')
}

fetchStudents()
</script>

<style scoped>
.page-wrap {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.header-row,
.actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
</style>
