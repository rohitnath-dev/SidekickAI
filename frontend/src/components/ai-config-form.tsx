import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Eye, EyeOff, Loader2, CheckCircle2, AlertCircle, ExternalLink } from 'lucide-react';
import { apiClient } from '@/lib/api-client';

interface AIConfigFormProps {
  onSaveSuccess: () => void;
  isSettingsMode?: boolean;
}

const OPENROUTER_MODELS = [
  { value: 'openrouter/free', label: 'OpenRouter Auto-Free (Recommended)' },
  { value: 'meta-llama/llama-3.3-70b-instruct:free', label: 'Llama 3.3 70B Instruct (Free)' },
  { value: 'google/gemini-2.5-flash', label: 'Gemini 2.5 Flash' },
  { value: 'openai/gpt-4o-mini', label: 'GPT-4o Mini' },
  { value: 'custom', label: 'Custom Model...' },
];

const OLLAMA_MODELS = [
  { value: 'llama3.2', label: 'Llama 3.2 (Recommended)' },
  { value: 'llama3.1', label: 'Llama 3.1' },
  { value: 'mistral', label: 'Mistral' },
  { value: 'gemma2', label: 'Gemma 2' },
  { value: 'phi3', label: 'Phi 3' },
  { value: 'custom', label: 'Custom Model...' },
];

export default function AIConfigForm({ onSaveSuccess, isSettingsMode = false }: AIConfigFormProps) {
  const queryClient = useQueryClient();

  // Selected provider: 'openrouter' or 'ollama'
  const [provider, setProvider] = useState<'openrouter' | 'ollama'>('openrouter');
  
  // OpenRouter inputs
  const [apiKey, setApiKey] = useState('');
  const [showApiKey, setShowApiKey] = useState(false);
  const [openRouterModel, setOpenRouterModel] = useState('openrouter/free');
  const [customOpenRouterModel, setCustomOpenRouterModel] = useState('');
  
  // Ollama inputs
  const [baseUrl, setBaseUrl] = useState('http://localhost:11434');
  const [ollamaModel, setOllamaModel] = useState('llama3.2');
  const [customOllamaModel, setCustomOllamaModel] = useState('');

  // Status states
  const [testStatus, setTestStatus] = useState<'idle' | 'testing' | 'success' | 'failed'>('idle');
  const [testError, setTestError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [hasTestedSuccessfully, setHasTestedSuccessfully] = useState(false);

  // Fetch existing config (if any)
  const { data: existingConfig, isLoading: isLoadingConfig } = useQuery({
    queryKey: ['user-ai-config'],
    queryFn: async () => {
      const response = await apiClient.get('/settings/ai-config');
      return response.data;
    },
    retry: false,
  });

  // Load existing config into fields
  useEffect(() => {
    if (existingConfig?.configured) {
      setProvider(existingConfig.provider);
      if (existingConfig.provider === 'openrouter') {
        // Set placeholder key so we don't overwrite if they don't type a new one
        if (existingConfig.has_api_key) {
          setApiKey('••••••••••••••••••••••••••••••••');
        }
        
        const isKnownModel = OPENROUTER_MODELS.some(m => m.value === existingConfig.model);
        if (isKnownModel) {
          setOpenRouterModel(existingConfig.model);
        } else {
          setOpenRouterModel('custom');
          setCustomOpenRouterModel(existingConfig.model);
        }
      } else {
        setBaseUrl(existingConfig.base_url || 'http://localhost:11434');
        const isKnownModel = OLLAMA_MODELS.some(m => m.value === existingConfig.model);
        if (isKnownModel) {
          setOllamaModel(existingConfig.model);
        } else {
          setOllamaModel('custom');
          setCustomOllamaModel(existingConfig.model);
        }
      }
      setHasTestedSuccessfully(true); // Treat existing config as pre-verified
    }
  }, [existingConfig]);

  // Reset verification status if fields change
  const handleFieldChange = (setter: any, value: any) => {
    setter(value);
    setHasTestedSuccessfully(false);
    setTestStatus('idle');
    setTestError(null);
  };

  const getActiveModel = () => {
    if (provider === 'openrouter') {
      return openRouterModel === 'custom' ? customOpenRouterModel : openRouterModel;
    } else {
      return ollamaModel === 'custom' ? customOllamaModel : ollamaModel;
    }
  };

  const handleTestConnection = async () => {
    setTestStatus('testing');
    setTestError(null);
    try {
      const activeModel = getActiveModel();
      if (!activeModel.trim()) {
        throw new Error('Model name is required.');
      }

      await apiClient.post('/settings/ai-config/test', {
        provider,
        model: activeModel,
        api_key: provider === 'openrouter' ? apiKey : null,
        base_url: provider === 'ollama' ? baseUrl : null,
      });

      setTestStatus('success');
      setHasTestedSuccessfully(true);
    } catch (err: any) {
      console.error(err);
      setTestStatus('failed');
      setHasTestedSuccessfully(false);
      setTestError(err.response?.data?.detail || err.message || 'Connection test failed.');
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    setSaveError(null);

    try {
      const activeModel = getActiveModel();
      if (!activeModel.trim()) {
        throw new Error('Model name is required.');
      }

      await apiClient.post('/settings/ai-config', {
        provider,
        model: activeModel,
        api_key: provider === 'openrouter' ? apiKey : null,
        base_url: provider === 'ollama' ? baseUrl : null,
      });

      // Invalidate core queries to refresh profile has_ai_config status and settings details
      queryClient.invalidateQueries({ queryKey: ['user'] });
      queryClient.invalidateQueries({ queryKey: ['user-settings'] });
      queryClient.invalidateQueries({ queryKey: ['user-ai-config'] });

      onSaveSuccess();
    } catch (err: any) {
      console.error(err);
      setSaveError(err.response?.data?.detail || err.message || 'Failed to save configuration.');
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoadingConfig) {
    return (
      <div className="py-12 flex flex-col items-center justify-center text-zinc-500">
        <Loader2 className="w-8 h-8 animate-spin text-zinc-400 mb-2" />
        <p className="text-xs font-mono tracking-widest uppercase">Loading configuration...</p>
      </div>
    );
  }

  return (
    <form onSubmit={handleSave} className="space-y-6">
      {/* Provider selection cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* OpenRouter Card */}
        <div
          onClick={() => handleFieldChange(setProvider as any, 'openrouter')}
          className={`cursor-pointer rounded-xl border p-5 flex flex-col justify-between transition-all duration-300 ${
            provider === 'openrouter'
              ? 'bg-indigo-500/10 border-indigo-500 shadow-lg shadow-indigo-500/5'
              : 'bg-zinc-900/20 border-zinc-900 hover:border-zinc-800'
          }`}
        >
          <div className="space-y-2">
            <div className="flex items-center gap-3">
              <input
                type="radio"
                name="provider"
                checked={provider === 'openrouter'}
                onChange={() => {}} // handled by parent div click
                className="accent-indigo-500 h-4 w-4"
              />
              <span className="font-bold text-sm text-zinc-100">OpenRouter</span>
            </div>
            <p className="text-xs text-zinc-400 leading-relaxed">
              Use an AI model through your own OpenRouter API key. Fast and hosted.
            </p>
          </div>
        </div>

        {/* Ollama Card */}
        <div
          onClick={() => handleFieldChange(setProvider as any, 'ollama')}
          className={`cursor-pointer rounded-xl border p-5 flex flex-col justify-between transition-all duration-300 ${
            provider === 'ollama'
              ? 'bg-indigo-500/10 border-indigo-500 shadow-lg shadow-indigo-500/5'
              : 'bg-zinc-900/20 border-zinc-900 hover:border-zinc-800'
          }`}
        >
          <div className="space-y-2">
            <div className="flex items-center gap-3">
              <input
                type="radio"
                name="provider"
                checked={provider === 'ollama'}
                onChange={() => {}} // handled by parent div click
                className="accent-indigo-500 h-4 w-4"
              />
              <span className="font-bold text-sm text-zinc-100">Ollama</span>
            </div>
            <p className="text-xs text-zinc-400 leading-relaxed">
              Run an LLM locally on your own computer using Ollama. Private and free.
            </p>
          </div>
        </div>
      </div>

      {/* Conditionally render settings inputs based on provider */}
      <div className="bg-zinc-900/30 border border-zinc-900 rounded-xl p-6 space-y-5">
        {provider === 'openrouter' ? (
          <div className="space-y-4">
            <h3 className="text-xs font-semibold text-zinc-200 uppercase tracking-wider">OpenRouter Settings</h3>
            
            {/* API Key */}
            <div className="space-y-2">
              <div className="flex justify-between items-center">
                <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-400">
                  API Key
                </label>
                <a
                  href="https://openrouter.ai/keys"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-indigo-400 hover:text-indigo-300 flex items-center gap-1 transition-colors"
                >
                  Get an OpenRouter API key
                  <ExternalLink className="w-3 h-3" />
                </a>
              </div>
              <div className="relative">
                <input
                  type={showApiKey ? 'text' : 'password'}
                  value={apiKey}
                  onChange={(e) => handleFieldChange(setApiKey, e.target.value)}
                  placeholder="Paste your sk-or-v1-... key"
                  className="w-full bg-zinc-950 border border-zinc-850 rounded-lg pl-3 pr-10 py-2.5 text-xs text-zinc-100 placeholder-zinc-600 outline-none focus:border-zinc-700 transition-all font-mono"
                />
                <button
                  type="button"
                  onClick={() => setShowApiKey(!showApiKey)}
                  className="absolute inset-y-0 right-0 flex items-center pr-3 text-zinc-500 hover:text-zinc-300"
                >
                  {showApiKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {/* Model Selection */}
            <div className="space-y-2">
              <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-400">
                Model
              </label>
              <select
                value={openRouterModel}
                onChange={(e) => handleFieldChange(setOpenRouterModel, e.target.value)}
                className="w-full bg-zinc-950 border border-zinc-850 rounded-lg px-3 py-2.5 text-xs text-zinc-100 outline-none focus:border-zinc-700 transition-all"
              >
                {OPENROUTER_MODELS.map((model) => (
                  <option key={model.value} value={model.value} className="bg-zinc-950">
                    {model.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Custom Model input */}
            {openRouterModel === 'custom' && (
              <div className="space-y-2 animate-fadeIn">
                <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-400">
                  Custom Model Name
                </label>
                <input
                  type="text"
                  value={customOpenRouterModel}
                  onChange={(e) => handleFieldChange(setCustomOpenRouterModel, e.target.value)}
                  placeholder="e.g. meta-llama/llama-3-8b-instruct:free"
                  className="w-full bg-zinc-950 border border-zinc-850 rounded-lg px-3 py-2.5 text-xs text-zinc-100 placeholder-zinc-650 outline-none focus:border-zinc-700 transition-all font-mono"
                />
              </div>
            )}
          </div>
        ) : (
          <div className="space-y-4">
            <h3 className="text-xs font-semibold text-zinc-200 uppercase tracking-wider">Ollama Local Settings</h3>
            
            <p className="text-xs text-zinc-450 leading-relaxed bg-zinc-950/45 border border-zinc-900 rounded-lg p-3">
              <span className="text-amber-500 font-semibold block mb-0.5">Local Requirement:</span>
              Ollama must be running on your computer. Make sure you run it with CORS enabled (Ollama enables this by default, but you might need to keep Ollama app active or run <code>ollama serve</code>).
            </p>

            {/* Base URL */}
            <div className="space-y-2">
              <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-400">
                Base URL
              </label>
              <input
                type="text"
                value={baseUrl}
                onChange={(e) => handleFieldChange(setBaseUrl, e.target.value)}
                placeholder="http://localhost:11434"
                className="w-full bg-zinc-950 border border-zinc-850 rounded-lg px-3 py-2.5 text-xs text-zinc-100 placeholder-zinc-600 outline-none focus:border-zinc-700 transition-all font-mono"
              />
            </div>

            {/* Model Selection */}
            <div className="space-y-2">
              <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-400">
                Model Name
              </label>
              <select
                value={ollamaModel}
                onChange={(e) => handleFieldChange(setOllamaModel, e.target.value)}
                className="w-full bg-zinc-950 border border-zinc-850 rounded-lg px-3 py-2.5 text-xs text-zinc-100 outline-none focus:border-zinc-700 transition-all"
              >
                {OLLAMA_MODELS.map((model) => (
                  <option key={model.value} value={model.value} className="bg-zinc-950">
                    {model.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Custom Model input */}
            {ollamaModel === 'custom' && (
              <div className="space-y-2 animate-fadeIn">
                <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-400">
                  Custom Model Name
                </label>
                <input
                  type="text"
                  value={customOllamaModel}
                  onChange={(e) => handleFieldChange(setCustomOllamaModel, e.target.value)}
                  placeholder="e.g. llama3.2:1b"
                  className="w-full bg-zinc-950 border border-zinc-850 rounded-lg px-3 py-2.5 text-xs text-zinc-100 placeholder-zinc-650 outline-none focus:border-zinc-700 transition-all font-mono"
                />
              </div>
            )}
          </div>
        )}

        {/* Test Connection Actions and Results */}
        <div className="pt-2 border-t border-zinc-900/60 flex flex-col gap-3">
          <div className="flex items-center justify-between gap-4">
            <span className="text-[10px] text-zinc-500">
              Test connection before saving.
            </span>
            <button
              type="button"
              onClick={handleTestConnection}
              disabled={testStatus === 'testing'}
              className="px-3.5 py-2 bg-zinc-950 hover:bg-zinc-900 border border-zinc-850 hover:border-zinc-700 rounded-lg text-xs font-semibold text-zinc-300 transition-all flex items-center gap-1.5 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {testStatus === 'testing' && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              {testStatus === 'testing' ? 'Testing...' : 'Test Connection'}
            </button>
          </div>

          {/* Test results alert */}
          {testStatus === 'success' && (
            <div className="flex items-start gap-2.5 rounded-lg border border-emerald-900/30 bg-emerald-950/15 p-3.5 text-xs text-emerald-400">
              <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-500 mt-0.5" />
              <span>Connection successful! Click save/continue to use this provider.</span>
            </div>
          )}

          {testStatus === 'failed' && testError && (
            <div className="flex items-start gap-2.5 rounded-lg border border-red-900/30 bg-red-950/15 p-3.5 text-xs text-red-400">
              <AlertCircle className="h-4 w-4 shrink-0 text-red-500 mt-0.5" />
              <div>
                <span className="font-semibold block">Connection failed</span>
                <span className="mt-0.5 block">{testError}</span>
              </div>
            </div>
          )}
        </div>
      </div>

      {saveError && (
        <div className="flex items-start gap-2.5 rounded-lg border border-red-900/30 bg-red-950/15 p-4 text-xs text-red-400">
          <AlertCircle className="h-4 w-4 shrink-0 text-red-500 mt-0.5" />
          <span>{saveError}</span>
        </div>
      )}

      {/* Form submission controls */}
      <div className="pt-2 flex justify-end">
        <button
          type="submit"
          disabled={isSaving || !hasTestedSuccessfully}
          className="flex items-center justify-center gap-1.5 px-6 py-2.5 rounded-lg bg-zinc-100 hover:bg-zinc-200 text-xs font-semibold text-zinc-950 transition-all cursor-pointer disabled:opacity-40 disabled:hover:bg-zinc-100 disabled:cursor-not-allowed shadow-md"
        >
          {isSaving && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
          {isSettingsMode ? 'Save AI Changes' : 'Continue to Dashboard'}
        </button>
      </div>
    </form>
  );
}
