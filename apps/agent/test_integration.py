"""
Test script to verify agent service integration with criteria_api.
Run this after starting both services to test the evaluation workflow.
"""

import asyncio
import httpx
import json


async def test_integration():
    """Test the complete evaluation workflow."""

    print("🧪 Testing Agent Service Integration with Criteria API\n")

    # Test 1: Check if both services are running
    print("1️⃣ Testing service health...")

    try:
        async with httpx.AsyncClient() as client:
            # Check criteria_api
            try:
                criteria_health = await client.get("http://localhost:8000/healthz")
                print(f"   ✅ Criteria API: {criteria_health.status_code}")
            except Exception as e:
                print(f"   ❌ Criteria API not reachable: {e}")
                print("   💡 Make sure criteria_api is running on port 8000")
                return

            # Check agent service
            try:
                agent_health = await client.get("http://localhost:8001/")
                print(f"   ✅ Agent Service: {agent_health.status_code}")
            except Exception as e:
                print(f"   ❌ Agent Service not reachable: {e}")
                print("   💡 Make sure agent service is running on port 8001")
                return

    except Exception as e:
        print(f"   ❌ Service health check failed: {e}")
        return

    # Test 2: List available rubrics from agent service
    print("\n2️⃣ Testing rubric listing...")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8001/evaluation/rubrics")

            print(f"   📊 Response Status: {response.status_code}")
            print(f"   📊 Response Headers: {dict(response.headers)}")

            try:
                rubrics_data = response.json()
                print(f"   📊 Response Body: {json.dumps(rubrics_data, indent=2)}")
            except Exception as json_error:
                print(f"   ❌ Failed to parse JSON response: {json_error}")
                print(f"   📊 Raw Response Text: {response.text}")
                return

            # Check if response has expected structure
            if not isinstance(rubrics_data, dict):
                print(f"   ❌ Expected dict response, got {type(rubrics_data)}")
                return

            if "status" not in rubrics_data:
                print(f"   ❌ Response missing 'status' field")
                print(f"   📊 Available fields: {list(rubrics_data.keys())}")
                return

            if rubrics_data["status"] == "success":
                rubrics = rubrics_data.get("rubrics", [])
                print(f"   ✅ Found {len(rubrics)} rubrics:")
                for rubric in rubrics:
                    print(f"      - {rubric.get('rubric_name', 'N/A')} (ID: {rubric.get('rubric_id', 'N/A')})")

                # Use first rubric for evaluation test
                if rubrics:
                    test_rubric_id = rubrics[0].get("rubric_id")
                    test_rubric_name = rubrics[0].get("rubric_name")
                    if not test_rubric_id:
                        print("   ⚠️ First rubric missing rubric_id field")
                        return
                else:
                    print("   ⚠️ No rubrics found - check if criteria_api has sample data")
                    return
            else:
                print(f"   ❌ API returned error status: {rubrics_data}")
                return

    except httpx.RequestError as e:
        print(f"   ❌ HTTP request failed: {e}")
        return
    except Exception as e:
        print(f"   ❌ Rubric listing failed: {e}")
        print(f"   📊 Exception type: {type(e).__name__}")
        return

    # Test 3: Get rubric details
    print(f"\n3️⃣ Testing rubric details for '{test_rubric_name}'...")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://localhost:8001/evaluation/rubrics/{test_rubric_id}")

            print(f"   📊 Response Status: {response.status_code}")

            try:
                rubric_details = response.json()
            except Exception as json_error:
                print(f"   ❌ Failed to parse JSON: {json_error}")
                print(f"   📊 Raw Response: {response.text}")
                return

            if rubric_details.get("status") == "success":
                rubric = rubric_details.get("rubric", {})
                criteria = rubric.get("criteria", [])
                criteria_count = len(criteria)
                print(f"   ✅ Rubric has {criteria_count} criteria")
                for criterion in criteria[:3]:  # Show first 3
                    desc = criterion.get('description', 'No description')
                    weight = criterion.get('weight', 'No weight')
                    print(f"      - {desc[:50]}... (weight: {weight})")
                if len(criteria) > 3:
                    print(f"      ... and {len(criteria) - 3} more criteria")
            else:
                print(f"   ❌ Failed to get rubric details: {rubric_details}")
                return

    except Exception as e:
        print(f"   ❌ Rubric details failed: {e}")
        return

    # Test 4: Evaluate candidates by ID (new workflow)
    print(f"\n4️⃣ Testing ID-based candidate evaluation...")

    # Example candidate IDs that should exist in Azure Search
    # In a real scenario, these would be actual candidate IDs from your index
    sample_candidate_ids = ["doc_001", "samsung_tv_review"]

    evaluation_request = {
        "rubric_id": test_rubric_id,
        "candidate_ids": sample_candidate_ids[:1],  # Single candidate test
        "comparison_mode": "deterministic",
        "ranking_strategy": "overall_score",
        "max_chunks": 10
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            print(f"   📤 Sending ID-based evaluation request for 1 candidate...")
            response = await client.post(
                "http://localhost:8001/evaluation/evaluate",
                json=evaluation_request
            )

            print(f"   📊 Evaluation Response Status: {response.status_code}")

            try:
                eval_result = response.json()
            except Exception as json_error:
                print(f"   ❌ Failed to parse evaluation JSON: {json_error}")
                print(f"   📊 Raw Response: {response.text}")
                return

            if eval_result.get("status") == "success":
                is_batch = eval_result.get("is_batch", False)
                print(f"   ✅ Evaluation completed! (Batch mode: {is_batch})")

                if is_batch:
                    batch_result = eval_result.get("batch_result", {})
                    total_candidates = batch_result.get("total_candidates", 0)
                    print(f"      Total Candidates: {total_candidates}")

                    comparison_summary = batch_result.get("comparison_summary", {})
                    best_candidate = comparison_summary.get("best_candidate", {})
                    if best_candidate:
                        print(f"      Best Candidate: {best_candidate.get('candidate_id')} (Score: {best_candidate.get('overall_score'):.2f})")
                else:
                    evaluation = eval_result.get("evaluation", {})
                    overall_score = evaluation.get("overall_score", 0)
                    candidate_id = evaluation.get("candidate_id", "Unknown")
                    criteria_evaluations = evaluation.get("criteria_evaluations", [])

                    print(f"      Candidate ID: {candidate_id}")
                    print(f"      Overall Score: {overall_score:.2f}/5.0")
                    print(f"      Criteria Evaluated: {len(criteria_evaluations)}")

                    # Show workflow metadata
                    agent_metadata = evaluation.get("agent_metadata", {})
                    workflow = agent_metadata.get("workflow", "unknown")
                    candidate_source = agent_metadata.get("candidate_source", "unknown")
                    print(f"      Workflow: {workflow}, Candidate Source: {candidate_source}")

            else:
                error_msg = eval_result.get('error', eval_result.get('message', 'Unknown error'))
                print(f"   ❌ Evaluation failed: {error_msg}")
                print(f"   📊 Full response: {json.dumps(eval_result, indent=2)}")
                return

    except httpx.TimeoutException:
        print(f"   ❌ Evaluation request timed out (>60s)")
        return
    except Exception as e:
        print(f"   ❌ ID-based evaluation failed: {e}")
        return

    # Test 5: Batch evaluation using IDs
    print(f"\n5️⃣ Testing batch evaluation with multiple candidate IDs...")

    batch_evaluation_request = {
        "rubric_id": test_rubric_id,
        "candidate_ids": sample_candidate_ids,  # Multiple candidates
        "comparison_mode": "deterministic",
        "ranking_strategy": "overall_score",
        "max_chunks": 10
    }

    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            print(f"   📤 Sending batch evaluation request for {len(sample_candidate_ids)} candidates...")
            response = await client.post(
                "http://localhost:8001/evaluation/evaluate",
                json=batch_evaluation_request
            )

            print(f"   📊 Batch Evaluation Response Status: {response.status_code}")

            try:
                batch_result = response.json()
            except Exception as json_error:
                print(f"   ❌ Failed to parse batch JSON: {json_error}")
                print(f"   📊 Raw Response: {response.text}")
                return

            if batch_result.get("status") == "success":
                is_batch = batch_result.get("is_batch", False)
                print(f"   ✅ Batch evaluation completed! (Batch mode: {is_batch})")

                if is_batch:
                    batch_data = batch_result.get("batch_result", {})
                    total_candidates = batch_data.get("total_candidates", 0)
                    print(f"      Total Candidates Evaluated: {total_candidates}")

                    comparison_summary = batch_data.get("comparison_summary", {})
                    best_candidate = comparison_summary.get("best_candidate", {})
                    rankings = comparison_summary.get("rankings", [])

                    if best_candidate:
                        print(f"      🏆 Best Candidate: {best_candidate.get('candidate_id')} (Score: {best_candidate.get('overall_score'):.2f})")

                    print(f"      📊 Candidate Rankings:")
                    for ranking in rankings[:3]:  # Show top 3
                        candidate_id = ranking.get('candidate_id', 'Unknown')
                        rank = ranking.get('rank', 0)
                        score = ranking.get('overall_score', 0)
                        print(f"        {rank}. {candidate_id}: {score:.2f}/5.0")

                    # Show workflow metadata
                    batch_metadata = batch_data.get("batch_metadata", {})
                    workflow = batch_metadata.get("workflow", "unknown")
                    candidate_source = batch_metadata.get("candidate_source", "unknown")
                    print(f"      Workflow: {workflow}, Candidate Source: {candidate_source}")

            else:
                error_msg = batch_result.get('error', batch_result.get('message', 'Unknown error'))
                print(f"   ❌ Batch evaluation failed: {error_msg}")
                print(f"   📊 Full response: {json.dumps(batch_result, indent=2)}")
                return

    except httpx.TimeoutException:
        print(f"   ❌ Batch evaluation request timed out (>90s)")
        return
    except Exception as e:
        print(f"   ❌ Batch evaluation failed: {e}")
        return

    print(f"\n🎉 All tests passed! ID-based evaluation workflow is working correctly.")
    print(f"\n📝 New Workflow Summary:")
    print(f"   - Input: rubric_id + candidate_id(s)")
    print(f"   - Agent fetches rubric from criteria_api")
    print(f"   - Agent fetches candidate text from Azure Search")
    print(f"   - Single candidate: returns evaluation result")
    print(f"   - Multiple candidates: returns batch evaluation with comparison")
    print(f"\n📝 Next steps:")
    print(f"   - Ensure your candidates are indexed in Azure Search")
    print(f"   - Use candidate IDs that exist in your search index")
    print(f"   - Create custom rubrics via criteria_api endpoints")
    print(f"   - Integrate with your candidate management system using IDs")


if __name__ == "__main__":
    asyncio.run(test_integration())