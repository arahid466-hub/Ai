"""Local-first, verification-first agent routing.
This module deliberately never reports success without a verifier result.
"""
from dataclasses import dataclass, field
from typing import Any, Callable
import re

@dataclass
class StepResult:
    name:str; status:str; result:Any=None; error:str|None=None

@dataclass
class AgentPlan:
    intent:str; steps:list[str]=field(default_factory=list)

class AutonomousAgent:
    intents={
      'coding':r'\b(code|python|javascript|fix|edit|build project)\b',
      'project':r'\b(project|workspace|create project)\b',
      'terminal':r'\b(run command|terminal|shell)\b',
      'android_builder':r'\b(apk|aab|android build|gradle)\b',
      'media':r'\b(video|audio|ffmpeg|compress|thumbnail)\b',
      'image_generation':r'\b(generate image|text to image|stable diffusion)\b',
      'tts':r'\b(speak|tts|text to speech|voice)\b',
      'apk_analysis':r'\b(analy[sz]e apk|manifest|permissions)\b',
      'security':r'\b(security|scan|fuzz|authorized test|api security)\b',
    }
    def classify(self,message:str)->str:
        for intent,pattern in self.intents.items():
            if re.search(pattern,message,re.I): return intent
        return 'chat'
    def plan(self,message:str)->AgentPlan:
        intent=self.classify(message)
        steps={'chat':['local_ai_chat','verify_response'],'coding':['inspect_context','apply_project_scoped_change','verify_change'], 'project':['validate_project_request','execute_project_operation','verify_project_state'], 'terminal':['validate_allowlist','execute_command','capture_exit_code'], 'android_builder':['detect_toolchain','build','verify_output'], 'media':['detect_ffmpeg','process_media','verify_output'], 'image_generation':['detect_local_image_engine','generate','verify_output'], 'tts':['detect_tts_engine','speak','verify_output'], 'apk_analysis':['validate_owned_artifact','analyze_apk','verify_report'], 'security':['validate_authorized_local_target','run_safe_check','verify_evidence']}[intent]
        return AgentPlan(intent,steps)
    def execute(self,message:str,tools:dict[str,Callable],verify:Callable[[str,Any],bool])->dict:
        plan=self.plan(message); results=[]
        for step in plan.steps:
            fn=tools.get(step)
            if not fn: results.append(StepResult(step,'not_available',error='Tool not registered')); return {'intent':plan.intent,'status':'not_available','steps':[vars(x) for x in results]}
            try:
                value=fn(message)
                if step==plan.steps[-1] and not verify(step,value): raise RuntimeError('Verification failed')
                results.append(StepResult(step,'completed',value))
            except Exception as exc:
                results.append(StepResult(step,'failed',error=str(exc))); return {'intent':plan.intent,'status':'failed','steps':[vars(x) for x in results]}
        return {'intent':plan.intent,'status':'completed','steps':[vars(x) for x in results]}
