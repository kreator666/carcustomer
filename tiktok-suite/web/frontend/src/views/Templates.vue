<template>
  <div>
    <el-card shadow="never" class="filter-card">
      <el-form inline @submit.prevent>
        <el-form-item label="语言">
          <el-select v-model="filters.lang" placeholder="全部" clearable style="width: 120px" @change="load">
            <el-option v-for="l in LANGS" :key="l" :label="l" :value="l" />
          </el-select>
        </el-form-item>
        <el-form-item label="动作">
          <el-select v-model="filters.action_type" placeholder="全部" clearable style="width: 120px" @change="load">
            <el-option v-for="t in ACTION_TYPES" :key="t.value" :label="t.label" :value="t.value" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="'Search'" @click="load">查询</el-button>
          <el-button :icon="'Refresh'" @click="reset">重置</el-button>
          <el-button type="success" :icon="'Plus'" @click="openEdit(null)">新增模板</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never">
      <el-table :data="rows" v-loading="loading">
        <el-table-column prop="name" label="名称" min-width="140" show-overflow-tooltip />
        <el-table-column prop="lang" label="语言" width="90" />
        <el-table-column label="动作" width="90">
          <template #default="{ row }">
            <el-tag :type="statusTag(ACTION_TYPES, row.action_type)">{{ statusLabel(ACTION_TYPES, row.action_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="body" label="内容" min-width="260" show-overflow-tooltip />
        <el-table-column label="启用" width="90">
          <template #default="{ row }">
            <el-switch :model-value="!!row.active" :loading="row._switching" @change="(v) => toggleActive(row, v)" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140">
          <template #default="{ row }">
            <el-button size="small" @click="openEdit(row)">编辑</el-button>
            <el-popconfirm title="确认删除该模板？" @confirm="remove(row)">
              <template #reference><el-button size="small" type="danger">删除</el-button></template>
            </el-popconfirm>
          </template>
        </el-table-column>
        <template #empty><el-empty description="暂无模板" /></template>
      </el-table>
    </el-card>

    <!-- 新增 / 编辑对话框 -->
    <el-dialog v-model="editVisible" :title="form.id ? '编辑模板' : '新增模板'" width="560px">
      <el-form label-width="80px">
        <el-form-item label="名称">
          <el-input v-model="form.name" placeholder="模板名称" />
        </el-form-item>
        <el-form-item label="语言">
          <el-select v-model="form.lang" style="width: 160px">
            <el-option v-for="l in LANGS" :key="l" :label="l" :value="l" />
          </el-select>
        </el-form-item>
        <el-form-item label="动作">
          <el-select v-model="form.action_type" style="width: 160px">
            <el-option v-for="t in ACTION_TYPES" :key="t.value" :label="t.label" :value="t.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="内容">
          <el-input v-model="form.body" type="textarea" :rows="5" placeholder="支持 {username} 等占位符（视后端实现）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" @click="save" :loading="saving">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue';
import { ElMessage } from 'element-plus';
import http from '../api';
import { ACTION_TYPES, LANGS, statusLabel, statusTag } from '../utils/constants';

const rows = ref([]);
const loading = ref(false);
const filters = reactive({ lang: '', action_type: '' });
const editVisible = ref(false);
const saving = ref(false);
const form = reactive({ id: null, name: '', lang: 'en', action_type: 'reply', body: '' });

async function load() {
  loading.value = true;
  try {
    const data = await http.get('/templates', { params: { ...filters } });
    rows.value = (data.items || []).map((r) => ({ ...r, _switching: false }));
  } finally {
    loading.value = false;
  }
}

function reset() {
  Object.assign(filters, { lang: '', action_type: '' });
  load();
}

function openEdit(row) {
  Object.assign(form, row
    ? { id: row.id, name: row.name, lang: row.lang, action_type: row.action_type, body: row.body }
    : { id: null, name: '', lang: 'en', action_type: 'reply', body: '' });
  editVisible.value = true;
}

async function save() {
  if (!form.name || !form.body) {
    ElMessage.warning('请填写名称和内容');
    return;
  }
  saving.value = true;
  try {
    const body = { name: form.name, lang: form.lang, action_type: form.action_type, body: form.body };
    if (form.id) await http.patch(`/templates/${form.id}`, body);
    else await http.post('/templates', body);
    ElMessage.success('已保存');
    editVisible.value = false;
    load();
  } finally {
    saving.value = false;
  }
}

async function toggleActive(row, val) {
  row._switching = true;
  try {
    const updated = await http.patch(`/templates/${row.id}`, { active: val ? 1 : 0 });
    row.active = updated.active;
  } finally {
    row._switching = false;
  }
}

async function remove(row) {
  await http.delete(`/templates/${row.id}`);
  ElMessage.success('已删除');
  load();
}

onMounted(load);
</script>

<style scoped>
.filter-card { margin-bottom: 12px; }
</style>
