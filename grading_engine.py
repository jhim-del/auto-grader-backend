import os
from openai import OpenAI
import json

# Initialize OpenAI client with stripped API key
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY").strip())

def grade_submission(task_prompt: str, user_prompt: str, num_runs: int = 3) -> dict:
    """
    Grade a user's prompt submission by running it 3 times and averaging the scores.
    
    Args:
        task_prompt: The assignment/task description
        user_prompt: The user's submitted prompt
        num_runs: Number of times to run the evaluation (default: 3)
    
    Returns:
        dict with average_score, detailed_scores, and feedback
    """
    
    scores = []
    feedbacks = []
    
    print(f"[GRADING_ENGINE] Starting grading with {num_runs} runs")
    
    for run in range(num_runs):
        try:
            print(f"[GRADING_ENGINE] Run {run + 1}/{num_runs}")
            
            # Execute the user's prompt
            execution_response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": task_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7
            )
            
            output = execution_response.choices[0].message.content
            print(f"[GRADING_ENGINE] Execution output length: {len(output)} chars")
            
            # Evaluate the output
            evaluation_prompt = f"""
당신은 프롬프트 평가 전문가입니다.

**과제 설명:**
{task_prompt}

**제출된 프롬프트:**
{user_prompt}

**프롬프트 실행 결과:**
{output}

다음 기준으로 제출된 프롬프트를 평가해주세요:

1. **과제 이해도 (20점)**: 프롬프트가 과제 요구사항을 정확히 이해했는가?
2. **명확성 (20점)**: 프롬프트가 명확하고 구체적인가?
3. **창의성 (20점)**: 독창적이고 효과적인 접근 방식인가?
4. **실행 결과 품질 (20점)**: 실제 출력물이 과제 목표를 달성했는가?
5. **완성도 (20점)**: 전체적으로 완성도가 높은가?

**응답 형식 (JSON):**
{{
    "score": <0-100 사이의 점수>,
    "feedback": "<구체적인 피드백 (200자 이내)>",
    "strengths": "<강점>",
    "improvements": "<개선점>"
}}
"""
            
            evaluation_response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a prompt evaluation expert. Always respond in valid JSON format."},
                    {"role": "user", "content": evaluation_prompt}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(evaluation_response.choices[0].message.content)
            score = result.get('score', 0)
            feedback = result.get('feedback', '')
            
            scores.append(score)
            feedbacks.append(feedback)
            
            print(f"[GRADING_ENGINE] Run {run + 1} score: {score}")
            
        except Exception as e:
            error_msg = f"프롬프트 실행 실패: {str(e)}"
            print(f"[GRADING_ENGINE ERROR] {error_msg}")
            raise Exception(error_msg)
    
    # Calculate average
    average_score = sum(scores) / len(scores)
    
    # Combine feedback
    combined_feedback = f"평균 점수: {average_score:.2f}점\n\n"
    combined_feedback += "각 실행별 점수: " + ", ".join([f"{s:.2f}점" for s in scores]) + "\n\n"
    combined_feedback += "종합 피드백:\n" + feedbacks[0]  # Use first feedback as representative
    
    print(f"[GRADING_ENGINE] ✓ Grading completed. Average: {average_score:.2f}")
    
    return {
        "average_score": round(average_score, 2),
        "detailed_scores": scores,
        "feedback": combined_feedback
    }
