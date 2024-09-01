
import streamlit as st
import time
import boto3
import json
import os
from botocore.exceptions import NoCredentialsError
from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips
from moviepy.video.fx import fadein, fadeout
import uuid
import image_generator as ImageGenerator


#########################################################################################################

# AWS S3 클라이언트 설정
s3 = boto3.client('s3')
bucket_name = 'iteams10-bucket'
upload_folder = '/home/ec2-user/environment/upload/'  # 로컬 파일 저장 경로
local_download_path = 'download/'
merged_file_path = 'merged/merged_video.mp4'
s3_upload_key = 'merged/merged_video.mp4'

# AWS S3에 파일 업로드 함수
def upload_to_s3(file_path, bucket_name):
    # 파일 이름과 확장자 추출
    base_name = os.path.basename(file_path)
    file_name, file_extension = os.path.splitext(base_name)
    
    # 유니크한 파일 이름 생성
    unique_file_name = f"{file_name}_{uuid.uuid4().hex}{file_extension}"
    file_key = f"uploaded/{unique_file_name}"
    
    try:
        s3.upload_file(file_path, bucket_name, file_key)
        print(f"File uploaded successfully to {bucket_name}/{file_key}")
        return file_key
    except FileNotFoundError:
        print(f"The file {file_path} was not found")
        return None
    except NoCredentialsError:
        print("Credentials not available")
        return None
    except Exception as e:
        print(f"Error occurred: {e}")
        return None
        
def upload_to_s3_merge(file_path, bucket_name, file_key):
    """로컬 파일을 S3에 업로드합니다."""
    try:
        s3.upload_file(file_path, bucket_name, file_key)
        print(f"Uploaded {file_path} to {bucket_name}/{file_key}")
    except FileNotFoundError:
        print(f"The file {file_path} was not found")
    except NoCredentialsError:
        print("Credentials not available")
    except Exception as e:
        print(f"Error occurred: {e}")
        
### S3 버킷에서 모든 mp4 파일의 키를 가져오기기
def list_mp4_files(bucket_name):
    response = s3.list_objects_v2(Bucket=bucket_name, Prefix='uploaded/')
    if 'Contents' in response:
        return [obj['Key'] for obj in response['Contents'] if obj['Key'].endswith('.mp4')]
    return []

### S3에서 파일을 다운로드드
def download_file_from_s3(bucket_name, s3_key, local_file_path):
    try:
        s3.download_file(bucket_name, s3_key, local_file_path)
        print(f"Downloaded {s3_key} to {local_file_path}")
    except FileNotFoundError:
        print(f"The file {s3_key} was not found")
    except NoCredentialsError:
        print("Credentials not available")
    except Exception as e:
        print(f"Error occurred: {e}")

### 영상 합치기
def merge_videos_with_audio(video_files, audio_file, output_file):
    # 동영상 파일들을 VideoFileClip으로 읽어오기
    clips = [VideoFileClip(video) for video in video_files]
    
    # 크로스페이드 효과 추가
    fade_duration = 0.5  # 전환 효과의 길이 (초)
    final_clips = []
    
    for i, clip in enumerate(clips):
        if i > 0:
            # 마지막으로 추가된 클립에 페이드아웃 적용
            previous_clip = final_clips[-1].fadeout(fade_duration)
            final_clips[-1] = previous_clip
        
        # 현재 클립을 리스트에 추가
        final_clips.append(clip)
    
    # 클립들을 연결하여 하나의 동영상으로 만듦
    final_video = concatenate_videoclips(final_clips, method="compose")
    
    # 오디오 파일 로드
    audio_clip = AudioFileClip(audio_file)
    
    # 동영상 길이와 오디오 길이를 맞추기 (필요 시 오디오를 반복 또는 자르기)
    audio_clip = audio_clip.subclip(0, final_video.duration)
    
    # 동영상에 오디오 추가
    final_video_with_audio = final_video.set_audio(audio_clip)
    
    # 최종 동영상 파일 출력
    final_video_with_audio.write_videofile(output_file, codec='libx264', audio_codec='aac')
    
def upload_video_to_s3(uploaded_file, bucket_name, upload_folder):
    # 로컬 파일 경로 설정
    local_file_path = os.path.join(upload_folder, uploaded_file.name)
    
    # 로컬에 파일 저장
    with open(local_file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    # S3 업로드
    s3_key = upload_to_s3(local_file_path, bucket_name)
    
    if s3_key:
        st.success("동영상 업로드에 성공했습니다!!")
    else:
        st.error("동영상 업로드에 실패했습니다...")
    
#########################################################################################################


def image_generator(image_target):
    body = json.dumps({"inputText": f"Translate {image_target} to English"})
    try:
        response = bedrock_runtime.invoke_model(
            body=body,
            modelId="amazon.titan-tg1-large"
        )

        response_body = json.loads(response['body'].read())
        resultEng = response_body["results"][0]["outputText"]
        
    except Exception as e:
        st.error(f"오류 발생: {e}")
    
    image_gen = ImageGenerator.ImageGenerator()
    imageLocation = image_gen.generate_image(f"{resultEng}, Make a picture that matches this sentence")
    
    return imageLocation



bedrock_runtime = boto3.client(service_name="bedrock-runtime", region_name="us-east-1")
#베드락 요청하는 함수
def get_response(messages):
    try:
        body = json.dumps(
            {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1000,
                "messages": [{"role": "user", "content": [{"type": "text", "text": messages}]}],
            }
        )

        response = bedrock_runtime.invoke_model(
            modelId="anthropic.claude-3-sonnet-20240229-v1:0",
            body=body,
        )
        response_body = json.loads(response.get("body").read())
        output_text = response_body["content"][0]["text"]
        return output_text
    except Exception as e:
        st.error(f"Error: {e}")
        return None



# Streamlit 세션 상태에서 현재 페이지를 추적하기 위한 초기 설정
if 'page' not in st.session_state:
    st.session_state['page'] = 'main'

if 'percent' not in st.session_state:
    st.session_state['percent'] = 0

# 다른 페이지로 이동하는 함수
def navigate_to(page):
    st.session_state['page'] = page
    st.rerun()

# 첫번째 페이지 내용 정의
def main_page():

    st.image("data/serendipity.png")
    st.header('🌴여행자의 정보를 입력해주세요!🌴')

    with st.form('my_form'):
    # 입력 위젯
       user_number = st.text_input('몇 명이 떠나나요?', value=st.session_state.get('user_number', ''))
       user_who = st.text_input('누구랑 가나요?', value=st.session_state.get('user_who', ''))
       user_transport = st.text_input('어떤 교통수단을 이용하시나요?', value=st.session_state.get('user_transport', ''))
       user_money = st.text_input('경비가 어떻게 되시나요?', value=st.session_state.get('user_money', ''))
       user_age = st.text_input('구성원의 나이가 어떻게 되시나요?', value=st.session_state.get('user_age', ''))
       user_gender = st.text_input('구성원의 성별이 어떻게 되시나요?', value=st.session_state.get('user_gender', ''))
        # 제출 버튼
       submitted = st.form_submit_button('제출')

    if submitted:
        st.session_state.user_number = user_number
        st.session_state.user_who = user_who
        st.session_state.user_transport = user_transport
        st.session_state.user_money = user_money
        st.session_state.user_age = user_age
        st.session_state.user_gender = user_gender

        total_msg = (
            f"{user_who}와 {user_number}명이 함께 여행을 가려고 해요. "
            f"구성원들의 성별은 {user_gender}이고, 나이는 {user_age}살입니다. "
            f"여행 경비는 {user_money}원이 될 예정이며, 이동할 때는 {user_transport}을 이용할 거예요. "
            f"이 정보를 고려해서 여행지 추천을 해주세요. 단 목적지는 꼭 단 1곳으로 추천해주세요. 하지만 유명한 곳은 제외해주세요 단 한국에서만!"
        )

        response = get_response(total_msg)
        if response:
            st.session_state.target = response
            navigate_to('second')
        else:
            st.error("Failed to get response from Bedrock")

    if 'target' in st.session_state:
        if st.button('다음 페이지로 이동'):
            navigate_to('second')

# 두번째 페이지 내용 정의
def second_page():

    st.image("data/serendipity.png")
    st.markdown("<h1 style='text-align: center; color: black;'>Serendipity</h1>", unsafe_allow_html=True)

    st.write("버튼을 클릭하여 여행지를 찾아보세요!")
    progress_bar = st.progress(0)

    
    if st.button("여행지 추천"):
        with st.spinner("추천 중..."):
            for percent_complete in range(100):
                time.sleep(0.05)
                progress_bar.progress(percent_complete + 1, text=f"Progress: {percent_complete + 1}%")
            if 'target' in st.session_state:
                st.write("목적지:", st.session_state.target)
            else:
                st.write("랜덤 목적지를 뽑아보세요!")
    if st.button('▶️'):
        navigate_to('third')


# 두번째 페이지 내용 정의
def third_page():
    st.image("data/serendipity.png")
    st.title('QUEST')

    progress_text = "Quest 진행 중..."
    progress_fraction = st.session_state['percent'] / 30  # 30 is the max value for percent
    bar = st.progress(progress_fraction, text=progress_text)

    col1, col2, col3 = st.columns(3)
    with col1: 
        st.image("data/foodimg.png")
        if st.button('FOOD'):
            target_food = f"{st.session_state.target}에서 가장 맛있는 음식 하나만 추천해줘 혹은 특별한 것 딱 하나만 추천해줘. 다른 말은 붙이지 말고 단답으로 대답해"
            target_food = get_response(target_food)
            if target_food:
                st.session_state.target_food = target_food
                st.session_state.page = 'sub'  # 페이지 상태 설정
            else:
                st.error("Failed to get response from Bedrock")
            navigate_to('fourth')
    with col2:
        st.image("data/activityimg.png")
        if st.button('ACTIVITY'):
            target_activity = f"{st.session_state.target}에서 가장 신나고 재미있는 곳 그렇지만 특별한 딱 하나만 추천해줘. 장소 이름만 단답으로 말해줘"
            target_activity = get_response(target_activity)
            if target_activity:
                st.session_state.target_activity = target_activity
                st.session_state.page = 'sub'  # 페이지 상태 설정
            else:
                st.error("Failed to get response from Bedrock")
            navigate_to('fifth')
    with col3:
        st.image("data/spotimg.png")
        if st.button('TOURIST SPOT'):
            target_spot = f"{st.session_state.target}에서 자연경관이 좋고 가장 화려한 곳 그렇지만 특별한 딱 하나만 추천해줘. 장소 이름만 단답으로 말해줘"
            target_spot = get_response(target_spot)
            if target_spot:
                st.session_state.target_spot = target_spot
                st.session_state.page = 'sub'  # 페이지 상태 설정
            else:
                st.error("Failed to get response from Bedrock")
            navigate_to('sixth')

    if st.session_state['percent'] == 30:
        if st.button('완성된 영상 보러가기'):
            navigate_to('seventh')

def fourth_page():
    st.image("data/serendipity.png")
    st.title('FOOD')
    if 'target_food' in st.session_state:
        st.image(image_generator(st.session_state.target_food))
        st.write("먹을 음식!!!!!:", st.session_state.target_food)
    else:
        st.write("음식점을 다시 뽑아보세요!")
    
    # 파일 업로드
    uploaded_file = st.file_uploader("영상을 업로드 하세요!", type=["mp4"])
    
    # 파일이 업로드된 경우에만 진행
    if uploaded_file is not None:
        if st.session_state['percent'] <= 25:
            st.session_state['percent'] += 5
        upload_video_to_s3(uploaded_file, bucket_name, upload_folder)
        
    if st.button('◀'):
        navigate_to('third')

def fifth_page():
    st.image("data/serendipity.png")
    st.title('ACTIVITY')
    if 'target_activity' in st.session_state:
        st.image(image_generator(st.session_state.target_activity))
        st.write("액티비티!!!!!:", st.session_state.target_activity)
    else:
        st.write("액티비티를 다시 뽑아주세요!")
        
    # 파일 업로드
    uploaded_file = st.file_uploader("영상을 업로드 하세요!", type=["mp4"])
    
    # 파일이 업로드된 경우에만 진행
    if uploaded_file is not None:
        if st.session_state['percent'] <= 25:
            st.session_state['percent'] += 5
        upload_video_to_s3(uploaded_file, bucket_name, upload_folder)
        
    if st.button('◀'):
        navigate_to('third')


def sixth_page():
    st.image("data/serendipity.png")
    st.title('TOURIST SPOT')
    if 'target_spot' in st.session_state:
        st.image(image_generator(st.session_state.target_spot))
        st.write("관광장소!!!!!:", st.session_state.target_spot)
    else:
        st.write("관광장소를 다시 뽑아주세요!")
        
    # 파일 업로드
    uploaded_file = st.file_uploader("영상을 업로드 하세요!", type=["mp4"])
    
    # 파일이 업로드된 경우에만 진행
    if uploaded_file is not None:
        if st.session_state['percent'] <= 25:
            st.session_state['percent'] += 5
        upload_video_to_s3(uploaded_file, bucket_name, upload_folder)
        
    if st.button('◀'):
        navigate_to('third')

def seventh_page():
    
    # S3에서 MP4 파일 목록 가져오기
    mp4_files = list_mp4_files(bucket_name)
    
    if mp4_files:
        selected_files = st.multiselect("영상 선택하기", options=mp4_files)
        
        if st.button("결과물 보기"):
            if selected_files:
                # 파일 다운로드
                local_paths = []
                for s3_key in selected_files:
                    local_file_path = os.path.join(local_download_path, os.path.basename(s3_key))
                    local_paths.append(local_file_path)
                    download_file_from_s3(bucket_name, s3_key, local_file_path)
                
                audio_file = "/home/ec2-user/environment/audio/Lost_Found.mp3"
                
                # 동영상 합치기
                merge_videos_with_audio(local_paths, audio_file, merged_file_path)
                
                # 합쳐진 파일 업로드
                upload_to_s3_merge(merged_file_path, bucket_name, s3_upload_key)
                
                st.success("결과물이 나왔습니다!!")
                st.video(f"https://{bucket_name}.s3.amazonaws.com/{s3_upload_key}")
            else:
                st.warning("No files selected.")
    else:
        st.warning("No MP4 files found in the bucket.")
    
    
    if st.button('이전 페이지로 이동'):
        navigate_to('third')
    if st.button('메인 페이지로 이동'):
        navigate_to('main')

# 페이지 네비게이션 로직
if st.session_state['page'] == 'main':
    main_page()
elif st.session_state['page'] == 'second':
    second_page()
elif st.session_state['page'] == 'third':
    third_page()
elif st.session_state['page'] == 'fourth':
    fourth_page()
elif st.session_state['page'] == 'fifth':
    fifth_page()
elif st.session_state['page'] == 'sixth':
    sixth_page()
elif st.session_state['page'] == 'seventh':
    seventh_page()
