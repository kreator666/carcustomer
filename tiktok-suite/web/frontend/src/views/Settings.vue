<template>
  <div v-loading="loading">
    <!-- 键值表单 -->
    <el-card shadow="never" title="系统设置">
      <template #header><span>系统设置</span></template>
      <el-form label-width="180px" style="max-width: 640px">
        <el-form-item label="每日回复上限">
          <el-input-number v-model="form.daily_reply_limit" :min="0" />
        </el-form-item>
        <el-form-item label="每日关注上限">
          <el-input-number v-model="form.daily_follow_limit" :min="0" />
        </el-form-item>
        <el-form-item label="每日私信上限">
          <el-input-number v-model="form.daily_dm_limit" :min="0" />
        </el-form-item>
        <el-form-item label="动作冷却(秒)">
          <el-input-number v-model="form.cooldown_seconds" :min="0" />
        </el-form-item>
        <el-form-item label="启用私信 (DM)">
          <el-switch v-model="dmEnabled" />
        </el-form-item>
        <el-form-item label="浏览器调试端口">
          <el-input v-model="form.browser_port" style="width: 200px" />
        </el-form-item>
        <el-form-item label="Chrome 路径">
          <el-input v-model="form.chrome_path" />
        </el-form-item>
        <el-form-item label="Chrome 配置目录">
          <el-input v-model="form.profile_dir" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="save" :loading="saving">保存</el-button>
          <el-button @click="load">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue';
import { ElMessage } from 'element-plus';
import http from '../api';

const loading = ref(false);
const saving = ref(false);
const form = reactive({
  daily_reply_limit: 20,
  daily_follow_limit: 30,
  daily_dm_limit: 5,
  cooldown_seconds: 20,
  dm_enabled: 'false',
  browser_port: '9222',
  chrome_path: '',
  profile_dir: '',
});

// dm_enabled 在 settings 里以字符串存储，这里用 switch 双向转换
const dmEnabled = computed({
  get: () => form.dm_enabled === 'true' || form.dm_enabled === true,
  set: (v) => { form.dm_enabled = v ? 'true' : 'false'; },
});

async function load() {
  loading.value = true;
  try {
    const data = await http.get('/settings');
    // data 为 {key: value}，填充已知键
    for (const k of Object.keys(form)) {
      if (data[k] !== undefined) form[k] = data[k];
    }
  } finally {
    loading.value = false;
  }
}

async function save() {
  saving.value = true;
  try {
    await http.put('/settings', { ...form });
    ElMessage.success('已保存');
  } finally {
    saving.value = false;
  }
}

onMounted(load);
</script>
